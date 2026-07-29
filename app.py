#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import httpx
import random
import re
import os
import time
import json
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
CORS(app)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

class ShopifyChecker:
    def __init__(self):
        self.ua = random.choice(USER_AGENTS)
    
    def get_headers(self, extra=None):
        headers = {
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
            'Cache-Control': 'max-age=0',
        }
        if extra:
            headers.update(extra)
        return headers

    async def find_product(self, session, site_url):
        """Try multiple methods to find a product"""
        
        # Method 1: /products.json
        print("🔍 Method 1: /products.json")
        try:
            resp = await session.get(f"{site_url}/products.json", headers=self.get_headers({'Accept': 'application/json'}))
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    return products[0]
        except:
            pass
        
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Method 2: /collections/all/products.json
        print("🔍 Method 2: /collections/all/products.json")
        try:
            resp = await session.get(f"{site_url}/collections/all/products.json", headers=self.get_headers({'Accept': 'application/json'}))
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    return products[0]
        except:
            pass
        
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Method 3: /products?limit=1
        print("🔍 Method 3: /products?limit=1")
        try:
            resp = await session.get(f"{site_url}/products?limit=1", headers=self.get_headers({'Accept': 'application/json'}))
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    return products[0]
        except:
            pass
        
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Method 4: Scrape HTML for product handle
        print("🔍 Method 4: HTML scraping")
        try:
            resp = await session.get(site_url, headers=self.get_headers())
            html = resp.text
            
            # Find product handle in HTML
            patterns = [
                r'/products/([a-zA-Z0-9\-]+)',
                r'productHandle":"([^"]+)"',
                r'data-product-handle="([^"]+)"',
                r'product\.handle\s*=\s*"([^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    handle = match.group(1)
                    print(f"✅ Found handle via HTML: {handle}")
                    # Try to get product JSON with this handle
                    resp = await session.get(f"{site_url}/products/{handle}.json", headers=self.get_headers({'Accept': 'application/json'}))
                    if resp.status_code == 200:
                        product = resp.json().get('product', {})
                        if product:
                            return product
        except:
            pass
        
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Method 5: Try /recommendations/products.json
        print("🔍 Method 5: /recommendations/products.json")
        try:
            resp = await session.get(f"{site_url}/recommendations/products.json", headers=self.get_headers({'Accept': 'application/json'}))
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                if products:
                    return products[0]
        except:
            pass
        
        # Method 6: Search for product in sitemap
        print("🔍 Method 6: Sitemap search")
        try:
            resp = await session.get(f"{site_url}/sitemap.xml", headers=self.get_headers())
            if resp.status_code == 200:
                xml = resp.text
                # Find product URLs in sitemap
                urls = re.findall(r'<loc>([^<]+/products/[^<]+)</loc>', xml)
                if urls:
                    product_url = urls[0]
                    handle = product_url.split('/products/')[-1].split('/')[0].split('?')[0]
                    resp = await session.get(f"{site_url}/products/{handle}.json", headers=self.get_headers({'Accept': 'application/json'}))
                    if resp.status_code == 200:
                        product = resp.json().get('product', {})
                        if product:
                            return product
        except:
            pass
        
        return None

    async def check_card(self, site_url, card):
        start = time.time()
        async with httpx.AsyncClient(follow_redirects=True, timeout=45.0) as session:
            try:
                parts = card.split('|')
                if len(parts) != 4:
                    return {"status": "ERROR", "message": "Invalid format"}
                
                cc, mon, year, cvv = parts
                
                # ============================================
                # STEP 1: Find product using multiple methods
                # ============================================
                print("🔎 Searching for product...")
                product = await self.find_product(session, site_url)
                
                if not product:
                    return {
                        "status": "ERROR", 
                        "message": "No product found on store after trying all methods",
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                # Extract product info
                variant_id = product['variants'][0]['id']
                product_handle = product.get('handle', '')
                price = product['variants'][0]['price']
                title = product.get('title', 'Unknown')
                
                print(f"✅ Found: {title} - ${price}")
                
                # ============================================
                # STEP 2: Warm up session
                # ============================================
                headers = self.get_headers()
                await session.get(site_url, headers=headers)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # ============================================
                # STEP 3: Add to cart
                # ============================================
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
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # ============================================
                # STEP 4: Get cart token
                # ============================================
                resp = await session.get(f"{site_url}/cart.js", headers=headers)
                try:
                    token = resp.json().get('token')
                    if not token:
                        return {
                            "status": "ERROR",
                            "message": "No cart token",
                            "time": f"{time.time() - start:.1f}s"
                        }
                except:
                    return {
                        "status": "ERROR",
                        "message": "Invalid cart response",
                        "time": f"{time.time() - start:.1f}s"
                    }
                
                # ============================================
                # STEP 5: Simple checkout
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
                
                # ============================================
                # STEP 6: Return result
                # ============================================
                elapsed = time.time() - start
                
                return {
                    "status": "PROCESSED",
                    "message": "Card submitted for processing",
                    "price": price,
                    "product": title,
                    "time": f"{elapsed:.1f}s"
                }
                
            except Exception as e:
                return {
                    "status": "ERROR",
                    "message": str(e)[:100],
                    "time": f"{time.time() - start:.1f}s"
                }

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'name': 'Shopify Card Checker v7.0',
        'endpoint': '/shopify?site=URL&cc=CARD'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

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
    print("🔥 Shopify Checker v7.0 running...")
    app.run(host='0.0.0.0', port=port, debug=False)
