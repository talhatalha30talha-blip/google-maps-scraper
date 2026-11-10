import asyncio
import json
import re
from config.config import SELECTORS

class GoogleMapsParser:

    @staticmethod
    async def extract_text_safely(page, selector):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                text = await locator.first.inner_text()
                return text.strip() if text else "N/A"
        except Exception:
            pass
        return "N/A"

    @staticmethod
    async def extract_reviews_count(page):
        try:
            selectors = [
                "button[jsaction*='pane.review']",
                "div.F7nice button",
                "span[aria-label*='review']",
                "button[aria-label*='review']"
            ]
            for sel in selectors:
                loc = page.locator(sel)
                cnt = await loc.count()
                for i in range(cnt):
                    aria = await loc.nth(i).get_attribute("aria-label")
                    if aria and "review" in aria.lower():
                        nums = re.findall(r'\d+', aria.replace(',', ''))
                        if nums:
                            return nums[-1]

            spans = page.locator("div.F7nice span")
            span_cnt = await spans.count()
            for i in range(span_cnt):
                txt = await spans.nth(i).inner_text()
                if txt and ("(" in txt or ")" in txt):
                    nums = re.findall(r'\d+', txt)
                    if nums:
                        return nums[0]

            rev_btn = page.locator("button[jsaction*='pane.review']")
            if await rev_btn.count() > 0:
                txt = await rev_btn.first.inner_text()
                nums = re.findall(r'\d+', txt.replace(',', ''))
                if nums:
                    return nums[-1]

        except Exception as e:
            print(f"[Warning] Review count extraction failed: {e}")
        return "N/A"

    @staticmethod
    def format_us_phone(phone_str):
        if not phone_str or phone_str == "N/A":
            return "N/A"
        digits = re.sub(r"\D", "", phone_str)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        return phone_str

    @classmethod
    async def extract_business_hours(cls, page):
        weekday_hours_array = []
        try:
            hours_container = page.locator("div[data-item-id='oh'], div.OqCZI")
            if await hours_container.count() > 0:
                try:
                    await hours_container.first.click()
                    await asyncio.sleep(1.5) # Wait for dropdown animation
                except Exception:
                    pass

                hour_rows = page.locator("tr.y0skZ, table.eKJIhd tr, div.t39ebf")
                row_count = await hour_rows.count()
                
                raw_texts = []
                if row_count > 0:
                    for r in range(row_count):
                        row_text = await hour_rows.nth(r).inner_text()
                        lines = [l.strip() for l in row_text.split('\n') if l.strip()]
                        raw_texts.extend(lines)
                else:
                    text = await hours_container.first.inner_text()
                    raw_texts = [line.strip() for line in text.split("\n") if line.strip()]

                days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                
                filtered_lines = []
                for line in raw_texts:
                    if line not in ["Open now", "Closed", "Suggest new hours", "Hide open hours for the week"]:
                        if not any(icon_marker in line for icon_marker in ["\ue8b5", "\ue5ce", "\ue14d"]):
                            filtered_lines.append(line)

                i = 0
                while i < len(filtered_lines):
                    current_item = filtered_lines[i]
                    matched_day = next((day for day in days_of_week if current_item.startswith(day)), None)
                    
                    if matched_day and i + 1 < len(filtered_lines):
                        next_item = filtered_lines[i + 1]
                        if "AM" in next_item or "PM" in next_item or "Closed" in next_item or "24 hours" in next_item:
                            weekday_hours_array.append(f"{matched_day}: {next_item}")
                            i += 2
                            continue
                    
                    if any(day in current_item for day in days_of_week) and ("AM" in current_item or "PM" in current_item or "24 hours" in current_item):
                        weekday_hours_array.append(current_item)
                    
                    i += 1

                if not weekday_hours_array:
                    weekday_hours_array = [l for l in filtered_lines if len(l) > 3]

                final_cleaned_hours = []
                for entry in weekday_hours_array:
                    cleaned_entry = (
                        entry.replace('\u202f', ' ')
                             .replace('\xa0', ' ')
                             .replace('\u2013', '-')
                             .replace('\u2014', '-')
                             .strip()
                    )
                    if cleaned_entry and len(cleaned_entry) > 3:
                        final_cleaned_hours.append(cleaned_entry)

                day_order_map = {
                    "Monday": 1,
                    "Tuesday": 2,
                    "Wednesday": 3,
                    "Thursday": 4,
                    "Friday": 5,
                    "Saturday": 6,
                    "Sunday": 7
                }

                def get_day_rank(item):
                    for day, rank in day_order_map.items():
                        if item.startswith(day):
                            return rank
                    return 99

                final_cleaned_hours.sort(key=get_day_rank)

                if final_cleaned_hours:
                    return json.dumps(final_cleaned_hours, ensure_ascii=False)
        except Exception as e:
            print(f"[Parser Warning] Could not parse hours: {e}")

        return json.dumps(["N/A"], ensure_ascii=False)

    @classmethod
    async def extract_filtered_reviews(cls, page):
        """Headless-proof review extractor with authentication check and dynamic scrolling."""
        filtered_reviews_set = set()
        try:
            # 1. Click the reviews tab using robust selectors & forced JS evaluation
            reviews_tab_selectors = [
                "button[aria-label*='Reviews']",
                "div[data-tab-index='1']",
                "button.hh2c6",
                "div[role='tab']"
            ]
            
            clicked = False
            for sel in reviews_tab_selectors:
                tabs = page.locator(sel)
                count = await tabs.count()
                for j in range(count):
                    try:
                        tab = tabs.nth(j)
                        text = await tab.inner_text()
                        if "review" in text.lower() or await tab.get_attribute("aria-label") and "review" in (await tab.get_attribute("aria-label")).lower():
                            await tab.evaluate("node => node.click()")
                            clicked = True
                            break
                    except Exception:
                        continue
                if clicked:
                    break
            
            if not clicked:
                await page.evaluate("""() => {
                    const elems = Array.from(document.querySelectorAll('button, div[role="tab"]'));
                    const target = elems.find(el => el.textContent.includes('Reviews') || (el.getAttribute('aria-label') || '').includes('Reviews'));
                    if (target) target.click();
                }""")

            await asyncio.sleep(3.0)  # Wait for review panel render

            prev_card_count = 0
            no_new_reviews_attempts = 0
            scroll_iteration = 0

            # 2. Infinite scroll and extraction loop (capped at 100 valid reviews)
            while len(filtered_reviews_set) < 100:
                # Extract currently visible review cards
                review_cards = page.locator("div.jftiEf")
                card_count = await review_cards.count()

                for i in range(card_count):
                    if len(filtered_reviews_set) >= 100:
                        break

                    card = review_cards.nth(i)
                    star_el = card.locator("span[aria-label*='star']")
                    if await star_el.count() > 0:
                        aria_label = await star_el.first.get_attribute("aria-label") or ""
                        rating_match = [int(s) for s in aria_label.split() if s.isdigit()]
                        if rating_match:
                            star_rating = rating_match[0]
                            if star_rating >= 3:
                                text_el = card.locator("span.wiI7pd")
                                if await text_el.count() > 0:
                                    comment = await text_el.first.inner_text()
                                    comment = (
                                        comment.replace("\n", " ")
                                               .replace('\u202f', ' ')
                                               .replace('\xa0', ' ')
                                               .replace('\u2013', '-')
                                               .strip()
                                    )
                                    if comment:
                                        filtered_reviews_set.add(f"[{star_rating}★] {comment}")

                if len(filtered_reviews_set) >= 100:
                    break

                scroll_iteration += 1

                # 3. Dynamic Scroll Engine with event dispatching
                scrolled = await page.evaluate("""() => {
                    const firstCard = document.querySelector('div.jftiEf');
                    if (!firstCard) return false;

                    let parent = firstCard.parentElement;
                    while (parent && parent !== document.body) {
                        const style = window.getComputedStyle(parent);
                        const overflowY = style.getPropertyValue('overflow-y');
                        if ((overflowY === 'auto' || overflowY === 'scroll' || parent.scrollHeight > parent.clientHeight)) {
                            const oldTop = parent.scrollTop;
                            parent.scrollTop = parent.scrollHeight;
                            
                            parent.dispatchEvent(new WheelEvent('wheel', { deltaY: 2500, bubbles: true, cancelable: true }));
                            
                            if (parent.scrollTop !== oldTop) return true;
                        }
                        parent = parent.parentElement;
                    }
                    
                    const feed = document.querySelector('div[role="feed"]') || document.querySelector('div.m6QErb');
                    if (feed) {
                        const oldTop = feed.scrollTop;
                        feed.scrollTop = feed.scrollHeight;
                        feed.dispatchEvent(new WheelEvent('wheel', { deltaY: 2500, bubbles: true, cancelable: true }));
                        return feed.scrollTop !== oldTop;
                    }
                    return false;
                }""")

                print(f"[*] Review Scroll Iteration #{scroll_iteration} | Dynamic Scroll Executed: {scrolled} | Unique Filtered Collected: {len(filtered_reviews_set)}/100")

                await asyncio.sleep(1.2)  # Allow network fetch time

                current_card_count = await review_cards.count()
                if current_card_count == prev_card_count:
                    no_new_reviews_attempts += 1
                    print(f"[!] No new reviews loaded attempt count: {no_new_reviews_attempts}/3")
                    if no_new_reviews_attempts >= 1:
                        print("[*] Reached absolute bottom or guest limit reached.")
                        break
                else:
                    no_new_reviews_attempts = 0
                        
                prev_card_count = current_card_count

            # 4. Safely navigate back to the main business overview pane
            back_btn = page.locator("button[aria-label='Back'], button.VfPpkd-icon-lg").first
            if await back_btn.count() > 0:
                await back_btn.evaluate("node => node.click()")
                await asyncio.sleep(1.0)

        except Exception as e:
            print(f"[Parser Warning] Could not extract reviews in headless mode: {e}")

        final_reviews_list = list(filtered_reviews_set)[:100]
        return json.dumps(final_reviews_list, ensure_ascii=False) if final_reviews_list else json.dumps(["N/A"], ensure_ascii=False)



    @classmethod
    async def parse_business_details(cls, page):
        await asyncio.sleep(1.0)

        name = await cls.extract_text_safely(page, SELECTORS["business_name"])
        rating = await cls.extract_text_safely(page, SELECTORS["business_rating"])
        reviews_count = await cls.extract_reviews_count(page)
        address = await cls.extract_text_safely(page, SELECTORS["business_address"])
        hours = await cls.extract_business_hours(page)
        
        raw_phone = await cls.extract_text_safely(page, SELECTORS["business_phone"])
        phone = cls.format_us_phone(raw_phone)
        
        website = await cls.extract_text_safely(page, SELECTORS["business_website"])
        plus_code = await cls.extract_text_safely(page, SELECTORS["plus_code"])
        reviews = await cls.extract_filtered_reviews(page)

        return {
            "name": name,
            "rating": rating,
            "reviews_count": reviews_count,
            "address": address,
            "hours": hours,
            "phone": phone,
            "website": website,
            "plus_code": plus_code,
            "reviews": reviews
        }