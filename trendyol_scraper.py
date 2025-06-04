from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
import os
import boto3
from io import BytesIO
from datetime import datetime

def start_scraping(category=None, save_to_s3=False, s3_bucket=None, user_interaction_needed=True):
    # Selenium WebDriver setup
    chrome_options = Options()
    
    # Add required arguments for Docker/containerized environment
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    # Only add headless if user interaction is not needed
    if not user_interaction_needed:
        chrome_options.add_argument("--headless")
    
    # Add window size
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Add remote debugging port
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Use chromedriver from PATH if in production, otherwise use the specified path
    if os.environ.get('DEPLOYMENT') == 'production':
        driver = webdriver.Chrome(options=chrome_options)
    else:
        service = Service(r'/Users/zeyneptz/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # URL to scrape
        url = "https://www.trendyol.com/cok-satanlar?type=bestSeller&webGenderId=1"
        driver.get(url)

        # Wait time for the page to load all products
        time.sleep(30)

        # Parse page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        snapshot_date = datetime.today().strftime('%Y-%m-%d')
        product_cards = soup.find_all('a', class_='product-card-container')
        product_data = []

        # Iterate over each product
        for card in product_cards:
            product_title = card.find('span', class_='product-name').text.strip() if card.find('span', class_='product-name') else None
            product_url = "https://www.trendyol.com" + card['href']
            product_brand = card.find('span', class_='product-brand').text.strip() if card.find('span', class_='product-brand') else None

            # Visit each product page to extract detailed information
            driver.get(product_url)
            time.sleep(3)  # Allow the product page to load

            product_soup = BeautifulSoup(driver.page_source, 'html.parser')
            product_price = None

            # Structure 1: 'product-price-container'
            product_price_container = product_soup.find('div', class_='product-price-container')
            if product_price_container:
                pr_bx_w = product_price_container.find('div', class_='pr-bx-w')
                if pr_bx_w:
                    pr_bx_nm = pr_bx_w.find('div', class_='pr-bx-nm with-org-prc')
                    if pr_bx_nm:
                        price_span = pr_bx_nm.find('span', class_='prc-dsc')
                        if price_span:
                            product_price = price_span.text.strip()

            # Structure 2 & 3: 'featured-price-box'
            if product_price is None:
                featured_price_box = product_soup.find('div', class_='featured-price-box')
                if featured_price_box:
                    featured_prices = featured_price_box.find('div', class_='featured-prices')
                    if featured_prices:
                        price_span = featured_prices.find('span', class_='prc-dsc')
                        if price_span:
                            product_price = price_span.text.strip()

            # Structure 4: 'campaign-price-box'
            if product_price is None:
                campaign_price_box = product_soup.find('div', class_='campaign-price-box')
                if campaign_price_box:
                    discounted_price = campaign_price_box.find('p', class_='discounted-price')
                    if discounted_price:
                        product_price = discounted_price.text.strip()

            # Fallback: 'price-container'
            if product_price is None:
                price_container = product_soup.find('div', class_='price-container')
                if price_container:
                    prices = price_container.find('div', class_='prices')
                    if prices:
                        price_item = prices.find('div', class_='price-item')
                        if price_item:
                            prc_box_dscntd = price_item.find('div', class_='prc-box-dscntd')
                            if prc_box_dscntd:
                                product_price = prc_box_dscntd.text.strip()

            print(product_price)

            # Extract original seller (Seller 0)
            seller_0_name = None
            seller_0_href = None
            seller_0_id = None
            seller_0_product_count = None
            seller_0_score = None
            seller_0_follower_count = None

            try:
                seller_0_div = product_soup.find('div', class_='widget-title product-seller-line')
                if seller_0_div:
                    seller_0_name = seller_0_div.find('a', class_='seller-name-text').text.strip() if seller_0_div.find('a', class_='seller-name-text') else None
                    seller_0_href = "https://www.trendyol.com" + seller_0_div.find('a', class_='seller-name-text')['href'] if seller_0_div.find('a', class_='seller-name-text') else None

                    # Extract follower count
                    follower_div = product_soup.find('div', class_='seller-follower-count') or product_soup.find('div', class_='followV2-text')
                    if follower_div:
                        seller_0_follower_count = follower_div.text.strip()

                    # Extract seller ID from the href
                    seller_0_id_match = re.search(r"-m-(\d+)", seller_0_href)
                    if seller_0_id_match:
                        seller_0_id = seller_0_id_match.group(1)

                        # Use the seller ID to construct the direct product count URL
                        seller_0_product_url = f"https://www.trendyol.com/sr?mid={seller_0_id}"
                        driver.get(seller_0_product_url)
                        time.sleep(3)  # Allow the page to load

                        try:
                            seller_0_product_count_element = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srch-ttl-cntnr-wrppr h2"))
                            )
                            if seller_0_product_count_element:
                                product_count_text = seller_0_product_count_element.text
                                match = re.search(r"(\d+)\s+sonuç", product_count_text)
                                seller_0_product_count = match.group(1) if match else None
                        except Exception as e:
                            print(f"Error fetching product count for original seller {seller_0_name}: {e}")

                        # Extract seller score
                        seller_0_score_div = seller_0_div.find('div', class_='sl-pn')
                        if seller_0_score_div:
                            seller_0_score = seller_0_score_div.text.strip()
            except Exception as e:
                print(f"Error extracting original seller information: {e}")

            # Extract review and rating details
            rating_score = None
            total_reviews = None
            total_comments = None
            barcode = None
            try:
                scripts = product_soup.find_all('script')
                for script in scripts:
                    if "window.__PRODUCT_DETAIL_APP_INITIAL_STATE__" in script.text:
                        json_text = re.search(r"window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*(\{.*?\});", script.string).group(1)
                        json_content = json.loads(json_text)

                        # Extract rating and reviews
                        rating_data = json_content.get("product", {}).get("ratingScore", {})
                        rating_score = rating_data.get("averageRating")
                        total_reviews = rating_data.get("totalRatingCount")
                        total_comments = rating_data.get("totalCommentCount")
                        
                        # Extract barcode
                        barcode = json_content.get('product', {}).get('variants', [{}])[0].get('barcode')
                        break
            except Exception as e:
                print(f"Error extracting product details for {product_url}: {e}")

            # Extract "Diğer Satıcılar" (Other Sellers)
            seller_info = []
            other_sellers_div = product_soup.find_all('div', class_='pr-mc-w gnr-cnt-br')
            for seller_div in other_sellers_div[:4]:  # Limit to 4 sellers
                try:
                    seller_name = seller_div.find('a', class_='seller-name-text').text.strip() if seller_div.find('a', class_='seller-name-text') else None
                    seller_href = "https://www.trendyol.com" + seller_div.find('a', class_='seller-name-text')['href'] if seller_div.find('a', class_='seller-name-text') else None
                    seller_id = re.search(r"mid=(\d+)", seller_href).group(1) if seller_href else None

                    # Extract seller price
                    seller_price = seller_div.find('div', class_='pr-bx-w').find('span', class_='prc-dsc').text.strip() if seller_div.find('div', class_='pr-bx-w') and seller_div.find('span', class_='prc-dsc') else None

                    # Extract seller score
                    seller_score_div = seller_div.find('div', class_='sl-pn')
                    seller_score = seller_score_div.text.strip() if seller_score_div else None

                    # Visit seller URL to get product count and follower count
                    seller_product_count = None
                    seller_follower_count = None
                    if seller_href:
                        driver.get(seller_href)
                        time.sleep(3)  # Allow the seller page to load
                        try:
                            seller_product_count_element = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srch-ttl-cntnr-wrppr h2"))
                            )
                            if seller_product_count_element:
                                product_count_text = seller_product_count_element.text
                                match = re.search(r"(\d+)\s+sonuç", product_count_text)
                                seller_product_count = match.group(1) if match else None

                            # Get follower count
                            follower_div = BeautifulSoup(driver.page_source, 'html.parser').find('div', class_='seller-follower-count') or BeautifulSoup(driver.page_source, 'html.parser').find('div', class_='followV2-text')
                            if follower_div:
                                seller_follower_count = follower_div.text.strip()
                        except Exception as e:
                            print(f"Error fetching seller info for {seller_name}: {e}")

                    # Append seller details with follower count
                    seller_info.append({
                        "Seller Name": seller_name,
                        "Seller ID": seller_id,
                        "Seller URL": seller_href,
                        "Seller Price": seller_price,
                        "Seller Score": seller_score,
                        "Seller Product Count": seller_product_count,
                        "Seller Follower Count": seller_follower_count
                    })
                except Exception as e:
                    print(f"Error extracting seller information: {e}")

            # Organize seller data into separate columns
            sellers_data = {}
            for i in range(4):  # Maximum 4 sellers
                seller_data = seller_info[i] if i < len(seller_info) else {}
                sellers_data.update({
                    f"Seller {i + 1} Name": seller_data.get("Seller Name"),
                    f"Seller {i + 1} ID": seller_data.get("Seller ID"),
                    f"Seller {i + 1} URL": seller_data.get("Seller URL"),
                    f"Seller {i + 1} Price": seller_data.get("Seller Price"),
                    f"Seller {i + 1} Score": seller_data.get("Seller Score"),
                    f"Seller {i + 1} Product Count": seller_data.get("Seller Product Count"),
                    f"Seller {i + 1} Follower Count": seller_data.get("Seller Follower Count")
                })

            # Append product data with seller details
            product_data.append({
                "Snapshot Date": snapshot_date,
                "Title": product_title,
                "Brand": product_brand,
                "Price": product_price,
                "Barcode": barcode,
                "Rating Score": rating_score,
                "Total Reviews": total_reviews,
                "Total Comments": total_comments,
                "URL": product_url,
                "Seller 0 Name": seller_0_name,
                "Seller 0 ID": seller_0_id,
                "Seller 0 URL": f"https://www.trendyol.com/sr?mid={seller_0_id}" if seller_0_id else None,
                "Seller 0 Product Count": seller_0_product_count,
                "Seller 0 Score": seller_0_score,
                "Seller 0 Follower Count": seller_0_follower_count,
                **sellers_data
            })

        # Create a DataFrame from the data
        df = pd.DataFrame(product_data)
        
        # Add category column if provided
        if category:
            df.insert(0, "Category", category)

        # Generate timestamp for the filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{category.lower() if category else 'latest'}.xlsx"
        
        # Save the data to S3 if requested, otherwise save locally
        if save_to_s3 and s3_bucket:
            try:
                s3_client = boto3.client('s3')
                # Save to BytesIO object
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False)
                excel_buffer.seek(0)
                
                # Upload to S3
                s3_key = f"scraped_data/{filename}"
                s3_client.upload_fileobj(excel_buffer, s3_bucket, s3_key)
                print(f"Data saved to S3 bucket: {s3_bucket}/{s3_key}")
                
                # Return the S3 path and dataframe
                return {
                    "s3_bucket": s3_bucket,
                    "s3_key": s3_key,
                    "filename": filename,
                    "data": df
                }
            except Exception as e:
                print(f"Error saving to S3: {str(e)}")
                # Fall back to local save if S3 fails
                output_file = filename
                df.to_excel(output_file, index=False)
                print(f"Data saved locally to {output_file} due to S3 error")
                return {"filename": output_file, "data": df}
        else:
            # Save locally
            output_file = filename
            df.to_excel(output_file, index=False)
            print(f"Data saved locally to {output_file}")
            return {"filename": output_file, "data": df}
        
    finally:
        driver.quit()

# Only run if this file is run directly (not when imported)
if __name__ == "__main__":
    start_scraping()
