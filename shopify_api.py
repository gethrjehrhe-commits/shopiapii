""" + "\033[0m")

import asyncio
from random import Random, random
import random
from time import time
from wsgiref import headers
from fake_useragent import UserAgent
import httpx
from bs4 import BeautifulSoup
import re
import json
import html
from urllib.parse import urlparse
import sys

# ... Kodun geri kalan kısmı aynı şekilde devam eder ...
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass 

def find_between(s, start, end):
    try:
        if start in s and end in s:
            return (s.split(start))[1].split(end)[0]
        return ""
    except:
        return ""

class ShopifyAuto:
    def __init__(self):
        self.user_agent = UserAgent().random
        self.last_price = None
    
    async def tokenize_card(self, session, cc, mon, year, cvv, first, last):
        """Tokenize card via Shopify Deposit Vault"""
        try:
            url = "https://deposit.us.shopifycs.com/sessions"
            payload = {
                "credit_card": {
                    "number": str(cc).replace(" ", ""),
                    "name": f"{first} {last}",
                    "month": int(mon),
                    "year": int(year),
                    "verification_value": str(cvv)
                }
            }
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Origin': 'https://checkout.shopifycs.com',
                'User-Agent': self.user_agent
            }
            r = await session.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                return r.json().get('id')
            else:
                print(f"❌ Failed to tokenize card: {r.text}")
                return None
        except Exception as e:
            print(f"❌ Tokenization error: {e}")
            return None

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
        
        valid_phones = [
            "2025550199", "3105551234", "4155559876", "6175550123",
            "9718081573", "2125559999", "7735551212", "4085556789"
        ]
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

async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as session:
        try:
            site = input('enter the shopify site url (e.g., https://site.com): ').strip().rstrip('/')
            site_url = site 
            
            card_input = input('enter card number (cc|mm|yy|cvv): ').strip()
            try:
                cc, mon, year, cvv = card_input.split('|')
            except ValueError:
                print("❌ Invalid card format. Using placeholders.")
                cc, mon, year, cvv = "0000000000000000", "01", "25", "123"
            
            shop = ShopifyAuto()
            
            product_header = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.6',
                'user-agent': shop.user_agent,
            }

            print("visiting the product page to get the variant id and cookies")
            try:
                product_response = await session.get(site + '/products.json', headers=product_header)
                products_data = product_response.json()
                product = products_data['products'][0]
                product_id = product['id']
                product_handle = product['handle']
                variant_id = product['variants'][0]['id']
                price = product['variants'][0]['price']
                
                print(f" ✅ Product: {product['title']}")
                print(f" ✅ Product ID: {product_id}")
                print(f" ✅ Variant ID: {variant_id}")
                print(f" ✅ Price: ${price}")
            except Exception as e:
                print(f"❌ Failed to fetch product info: {e}")
                return

            print("\n Visiting product page to get cookies...")
            product_page_response = await session.get(f"{site}/products/{product_handle}", headers=product_header)
            print(f"   Status: {product_page_response.status_code}")

            product_header.update({'user-agent': UserAgent().random}) 

            await session.get(site + '/cart.js', headers=product_header)

            add_data = {
                'id': str(variant_id),
                'quantity': '1',
                'form_type': 'product',
            }

            print("\n Adding item to cart...")
            response = await session.post(site + '/cart/add.js', headers=product_header, data=add_data)
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ Item added to cart!")
                
                cart_response = await session.get(f"{site}/cart.js", headers=product_header)
                cart_data = cart_response.json()
                token = cart_data['token']
                print(f"   Cart token: {token}")
                print(f"   Items in cart: {cart_data['item_count']}")
                
                print ('now you will be redirected to the checkout page, wait.....')
                
                checkout_headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': site,
                    'referer': f"{site}/cart",
                    'upgrade-insecure-requests': '1',
                    'user-agent': product_header['user-agent'],
                }
                
                await session.get(f"{site}/checkout", headers=checkout_headers) 
                
                checkout_data = {
                    'checkout': '',  
                    'updates[]': '1', 
                }
                
                checkout_response = await session.post(f"{site}/cart", headers=checkout_headers, data=checkout_data)
                
                print(f"   Final URL after redirect: {checkout_response.url}")

                response_text2 = checkout_response.text

                x_checkout_one_session_token = re.search(
                    r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', 
                    response_text2
                )

                session_token = None
                if x_checkout_one_session_token:
                    session_token = x_checkout_one_session_token.group(1)
                    print(f" ✅Full session token length: {len(session_token)}")
                    print(f" ✅Session token: {session_token}")

                queue_token = find_between(response_text2, 'queueToken&quot;:&quot;', '&quot;')
                print(f" ✅queue_token={queue_token}")
                stable_id = find_between(response_text2, 'stableId&quot;:&quot;', '&quot;')
                print(f" ✅stable_id={stable_id}")
                paymentMethodIdentifier = find_between(response_text2, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
                print(f" ✅paymentMethodIdentifier={paymentMethodIdentifier}")

                await asyncio.sleep(1)

                print("\n STEP 5: Creating payment session...")
                random_info = await shop.get_random_info()
                fname = random_info["fname"]
                lname = random_info["lname"]
                email = random_info["email"]
                phone = random_info["phone"]
                add1 = random_info["add1"]
                city = random_info["city"]
                state_short = random_info["state_short"]
                zip_code = str(random_info["zip"])

                print(f" Using address: {add1}, {city}, {state_short} {zip_code}")
                print(f" Using phone: {phone}")

                session_endpoints = [
                    "https://deposit.us.shopifycs.com/sessions",
                    "https://checkout.pci.shopifyinc.com/sessions",
                    "https://checkout.shopifycs.com/sessions"
                ]
                        
                session_created = False
                sessionid = None
                        
                for endpoint in session_endpoints:
                    try:
                        print(f" Trying payment session endpoint: {endpoint}")
                        headers = {
                            'authority': urlparse(endpoint).netloc,
                            'accept': 'application/json',
                            'content-type': 'application/json',
                            'origin': 'https://checkout.shopifycs.com',
                            'referer': 'https://checkout.shopifycs.com/',
                            'user-agent': shop.user_agent,
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
                        print(f" Payment Session Response Status from {endpoint}: {session_response.status_code}")
                                
                        if session_response.status_code == 200:
                            session_data = session_response.json()
                            if "id" in session_data:
                                sessionid = session_data["id"]
                                session_created = True
                                print(f"✅ Payment session created at {endpoint}: {sessionid}")
                                break
                        else:
                            print(f"⚠️ {endpoint} returned {session_response.status_code}")
                    except Exception as e:
                        print(f"⚠️ Error trying {endpoint}: {e}")

                if session_created:
                    await asyncio.sleep(1)
                    print("\n Submitting GraphQL payment...")
                    
                    graphql_url = f"{site_url}/checkouts/unstable/graphql"
                    
                    graphql_headers = {
                        'authority': urlparse(site_url).netloc,
                        'accept': 'application/json',
                        'accept-language': 'en-US,en;q=0.9',
                        'content-type': 'application/json',
                        'origin': site_url,
                        'referer': f"{site_url}/",
                        'user-agent': shop.user_agent,
                        'x-checkout-one-session-token': session_token,
                        'x-checkout-web-deploy-stage': 'production',
                        'x-checkout-web-server-handling': 'fast',
                        'x-checkout-web-source-id': token,
                    }

                    random_page_id = f"{random.randint(10000000, 99999999):08x}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(1000, 9999):04X}-{random.randint(100000000000, 999999999999):012X}"

                if session_created:
                    await asyncio.sleep(1)
                    
                    graphql_url = f"{site_url}/checkouts/unstable/graphql"
                    

                    tokens = {
                        'x_checkout_one_session_token': session_token,
                        'queue_token': queue_token,
                        'stable_id': stable_id,
                        'paymentMethodIdentifier': paymentMethodIdentifier
                    }


                    for attempt in range(2):
                        print(f"\n Submitting GraphQL payment (Attempt {attempt + 1})...")
                        
                        graphql_headers = {
                            'authority': urlparse(site_url).netloc,
                            'accept': 'application/json',
                            'accept-language': 'en-US,en;q=0.9',
                            'content-type': 'application/json',
                            'origin': site_url,
                            'referer': f"{site_url}/",
                            'user-agent': shop.user_agent,
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
                                    'sessionInput': {
                                        'sessionToken': session_token,
                                    },
                                    'queueToken': queue_token,
                                    'discounts': {
                                        'lines': [],
                                        'acceptUnexpectedDiscounts': True,
                                    },
                                    'delivery': {
                                        'deliveryLines': [
                                            {
                                                'selectedDeliveryStrategy': {
                                                    'deliveryStrategyMatchingConditions': {
                                                        'estimatedTimeInTransit': {'any': True},
                                                        'shipments': {'any': True},
                                                    },
                                                    'options': {},
                                                },
                                                'targetMerchandiseLines': {
                                                    'lines': [{'stableId': stable_id}],
                                                },
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
                                            },
                                        ],
                                        'noDeliveryRequired': [],
                                        'useProgressiveRates': False,
                                        'prefetchShippingRatesStrategy': None,
                                    },
                                    'merchandise': {
                                        'merchandiseLines': [
                                            {
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
                                            },
                                        ],
                                    },
                                    'payment': {
                                        'totalAmount': {'any': True},
                                        'paymentLines': [
                                            {
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
                                            },
                                        ],
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
                                            'emailOrSms': {
                                                'value': email,
                                                'emailOrSmsChanged': False,
                                            },
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
                        print(f" ✅GraphQL Response Status: {graphql_response.status_code}")
                        
                        if graphql_response.status_code == 200:
                            result_data = graphql_response.json()
                            print(f"✅ GraphQL Response: {json.dumps(result_data, indent=2)[:1000]}...")
                            
                            receipt_id = None
                            error_codes = []
                            
                            completion = result_data.get('data', {}).get('submitForCompletion', {})
                            
                            if completion.get('receipt'):
                                receipt_id = completion['receipt'].get('id')
                                print(f"✅ Receipt ID extracted: {receipt_id}")
                            
                            if completion.get('__typename') == 'Throttled':
                                print(" Throttled response detected - payment is being processed...")
                            
                            if completion.get('errors'):
                                errors = completion['errors']
                                error_codes = [e.get('code') for e in errors if 'code' in e]
                                print(f"⚠️ Errors returned: {error_codes}")
                                

                                soft_errors = ['TAX_NEW_TAX_MUST_BE_ACCEPTED', 'WAITING_PENDING_TERMS']
                                

                                only_soft_errors = all(code in soft_errors for code in error_codes)
                                if only_soft_errors and attempt == 0:
                                    print(" Soft errors detected (Tax/Terms), retrying submission...")
                                    await asyncio.sleep(2)
                                    continue
                                
                                non_soft_errors = [code for code in error_codes if code not in soft_errors]
                                if non_soft_errors:
                                    print(f"❌ Payment Rejected: {', '.join(non_soft_errors)}")
                                    return
                            
                            if completion.get('reason'):
                                print(f"❌ Payment Failed: {completion['reason']}")
                                return
                            
                            if receipt_id:
                                print(f"\n Polling for receipt status...")
                                poll_payload = {
                                    'query': 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}__typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}',
                                    'variables': {
                                        'receiptId': receipt_id,
                                        'sessionToken': session_token,
                                    },
                                    'operationName': 'PollForReceipt'
                                }
                                
                                for poll_attempt in range(10):
                                    await asyncio.sleep(3)
                                    print(f"Poll attempt {poll_attempt + 1}/10...")
                                    poll_response = await session.post(graphql_url, headers=graphql_headers, json=poll_payload)
                                    if poll_response.status_code == 200:
                                        poll_data = poll_response.json()
                                        receipt = poll_data.get('data', {}).get('receipt', {})
                                        
                                        if receipt.get('__typename') == 'ProcessedReceipt' or 'orderIdentity' in receipt:
                                            order_id = receipt.get('orderIdentity', {}).get('id', 'N/A')
                                            print(f"✅ CARD CHARGED! 💰🔥 Order ID: {order_id}")
                                            return
                                        elif receipt.get('__typename') == 'ActionRequiredReceipt':
                                            print(f"✅ Card APPROVED! ✅ (Action required - 3D Secure)")
                                            print(f"📡 Full 3DS Response: {json.dumps(poll_data, indent=2)}")
                                            return
                                        elif receipt.get('__typename') == 'FailedReceipt':
                                            print(f"❌ Card DECLINED")
                                            print(f"📡 Full Decline Response: {json.dumps(poll_data, indent=2)}")
                                            return
                                        else:
                                            print(f"📡 Poll response (Typename: {receipt.get('__typename')}): {json.dumps(poll_data, indent=2)}")
                                break

                        else:
                            print(f"⚠️ GraphQL submission failed: {graphql_response.status_code}")
                            if attempt == 0:
                                await asyncio.sleep(2)
                                continue
                            return
                    
                    print("\n🔍 STEP 8: Checking final result...")
                    checkout_url_final = f"{site_url}/checkout?from_processing_page=1&validate=true"
                    final_response = await session.get(checkout_url_final)
                    final_url = str(final_response.url)
                    print(f"📍 Final URL: {final_url}")
                    
                    if "/thank" in final_url.lower() or "/orders/" in final_url:
                        print(f"✅ CARD CHARGED! Payment Successful! 💰")
                    else:
                        print(f"⚠️ Unknown Status - Manual check needed: {final_url}")

        except Exception as e:
            print(f"❌ An error occurred in main: {e}")

        except Exception as e:
            print(f"❌ An error occurred in main: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user, exiting.")
