import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os

def download_and_create_pdf(url, output_pdf_name):
    print(f"Fetching content from {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all images with 'wp-image' in their class, as discovered
    all_imgs = soup.find_all('img')
    image_urls = []
    for img in all_imgs:
        classes = img.get('class', [])
        if any('wp-image' in c for c in classes):
            if img.get('src'):
                image_urls.append(img['src'])
    
    if not image_urls:
        print("No images found with the expected class.")
        return

    print(f"Found {len(image_urls)} images. Downloading...")

    images = []
    for i, img_url in enumerate(image_urls):
        try:
            print(f"Downloading image {i+1}/{len(image_urls)}: {img_url}")
            img_response = requests.get(img_url, headers=headers)
            img_response.raise_for_status()
            
            img_data = BytesIO(img_response.content)
            img = Image.open(img_data)
            
            # Convert to RGB to ensure compatibility with PDF (remove alpha channel if png)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            images.append(img)
        except Exception as e:
            print(f"Error downloading image {img_url}: {e}")

    if images:
        print(f"Saving {len(images)} images to {output_pdf_name}...")
        images[0].save(
            output_pdf_name, "PDF", resolution=100.0, save_all=True, append_images=images[1:]
        )
        print("PDF created successfully!")
    else:
        print("No images successfully downloaded.")

if __name__ == "__main__":
    target_urls = [
        "https://sakamotodays.org/comic/sakamoto-days-chapter-109/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-110/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-111/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-112/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-113/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-114/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-115/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-116/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-117/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-118/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-119/",
        "https://sakamotodays.org/comic/sakamoto-days-chapter-120/",
    ]

    for url in target_urls:
        try:
            # Generate a dynamic output filename from the URL
            # e.g., "https://sakamotodays.org/comic/sakamoto-days-chapter-97/" -> "sakamoto-days-chapter-97"
            slug = url.strip('/').split('/')[-1]
            # e.g., "sakamoto-days-chapter-97" -> "Sakamoto_Days_Chapter_97.pdf"
            output_filename = slug.replace('-', '_').title() + ".pdf"
            
            download_and_create_pdf(url, output_filename)
            print("-" * 50)
        except Exception as e:
            print(f"An error occurred while processing {url}: {e}")
            print("-" * 50)
