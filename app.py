#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import httpx
import random
import re
import os
import time
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
CORS(app)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

class ShopifyChecker:
    def __init__(self):
        self.ua = random.choice(USER_AGENTS)
    
    def get_headers(self, extra=None):
        headers = {
            'User-Agent': self.ua,
            'Accept': 'application/json,text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        if extra:
            headers.update(extra)
        return headers

    async def get_cheapest_product(self, session, site_url):
        """Get the cheapest product from store - FAST"""
        
        # Try /products.json first (fastest)
        try:
            resp = await session.get(
                f"{site_url}/products.json?limit=10", 
                headers=self.get_headers(),
                timeout=10.0
            )
            
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    # Find cheapest product
                    cheapest = None
                    cheapest_price = float('inf')
                    
                    for p in products:
                        for variant in p.get('variants', []):
                            price = float(variant.get('price', 999999))
                            if price < cheapest_price:
                                cheapest_price = price
                                cheapest = {
                                    'product': p,
                                    'variant': variant,
                                    'price': price
                                }
                    
                    if cheapest:
                        print(f"✅ Cheapest: ${cheapest['price']} - {cheapest['product'].get('title', 'Unknown')}")
                        return cheapest
        except:
            pass
        
        # Fallback: try /collections/all/products.json
        try:
            resp = await session.get(
                f"{site_url}/collections/all/products.json?limit=10",
                headers=self.get_headers(),
                timeout=10.0
            )
            
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    cheapest = None
                    cheapest_price = float('inf')
                    
                    for p in products:
                        for variant in p.get('variants', []):
                            price = float(variant.get('price', 999999))
                            if price < cheapest_price:
                                cheapest_price = price
                                cheapest = {
                                    'product': p,
                                    'variant': variant,
                                    'price': price
                                }
                    
                    if cheapest:
                        print(f"✅ Cheapest: ${cheapest['price']}")
                        return cheapest
        except:
            pass
        
        return None

    async def check_card(self, site_url, card):
        start = time.time()
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "message": "Invalid format"}
                
                cc, mon, year, cvv = parts
                
                # ============================================
                # STEP 1: Get cheapest product (FAST)
                # ============================================
                print("🔍 Finding cheapest product...")
                product_data = await self.get_cheapest_product(session, site_url)
                
                if not product_data:
                    return {
                        "status": "ERROR",
                        "message": "No products found",
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                variant_id = product_data['variant']['id']
                price = product_data['price']
                product_title = product_data['product'].get('title', 'Unknown')
                variant_title = product_data['variant'].get('title', 'Default')
                
                print(f"✅ {product_title} - ${price} ({variant_title})")
                
                # ============================================
                # STEP 2: Add to cart (FAST)
                # ============================================
                headers = self.get_headers()
                
                # Visit cart page first
                await session.get(f"{site_url}/cart.js", headers=headers)
                
                # Add to cart
                resp = await session.post(
                    f"{site_url}/cart/add.js",
                    headers=self.get_headers({
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': site_url,
                    }),
                    data={
                        'id': str(variant_id),
                        'quantity': '1',
                        'form_type': 'product'
                    },
                    timeout=10.0
                )
                
                if resp.status_code != 200:
                    return {
                        "status": "ERROR",
                        "message": f"Cart failed: {resp.status_code}",
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                # ============================================
                # STEP 3: Get token
                # ============================================
                resp = await session.get(f"{site_url}/cart.js", headers=headers, timeout=10.0)
                token = resp.json().get('token')
                
                if not token:
                    return {
                        "status": "ERROR",
                        "message": "No token",
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                # ============================================
                # STEP 4: Fast checkout attempt
                # ============================================
                checkout_headers = self.get_headers({
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': site_url,
                    'Referer': f"{site_url}/cart"
                })
                
                # Visit checkout
                await session.get(f"{site_url}/checkout", headers=checkout_headers, timeout=10.0)
                
                # Submit cart
                resp = await session.post(
                    f"{site_url}/cart",
                    headers=checkout_headers,
                    data={'checkout': '', 'updates[]': '1'},
                    timeout=10.0
                )
                
                elapsed = time.time() - start
                
                # ============================================
                # STEP 5: Return result
                # ============================================
                return {
                    "status": "PROCESSED",
                    "message": "Card submitted",
                    "price": f"${price}",
                    "product": product_title,
                    "variant": variant_title,
                    "token": token[:20] + "...",
                    "time": f"{elapsed:.1f}s"
                }
                
            except httpx.TimeoutException:
                return {
                    "status": "ERROR",
                    "message": "TIMEOUT",
                    "time": f"{time.time() - start:.1f}s"
                }
            except Exception as e:
                return {
                    "status": "ERROR",
                    "message": str(e)[:80],
                    "time": f"{time.time() - start:.1f}s"
                }

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'name': 'Shopify Card Checker v8.0 - FAST',
        'endpoint': '/shopify?site=URL&cc=CARD',
        'features': ['Cheapest product auto-select', 'Fast checkout']
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/shopify', methods=['GET'])
def shopify():
    try:
        site = request.args.get('site')
        cc = request.args.get('cc')
        
        if not site or not cc:
            return jsonify({'error': 'Missing site or cc'}), 400
        
        if not site.startswith('http'):
            site = 'https://' + site
        
        result = asyncio.run(ShopifyChecker().check_card(site, cc))
        return jsonify({
            'site': site,
            'cc': cc,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("""
    ╔══════════════════════════════════════╗
    ║   🔥 Shopify Checker v8.0 - FAST    ║
    ║   📡 /shopify?site=URL&cc=CARD      ║
    ║   ⚡ Cheapest product auto-select   ║
    ╚══════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
