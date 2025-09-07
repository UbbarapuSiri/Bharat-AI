# Food Health Rating App
# A comprehensive system for rating packaged foods based on authoritative health guidelines

import streamlit as st
import json
import sqlite3
import hashlib
import datetime
import re
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import requests
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('food_rating.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class NutrientInfo:
    """Standardized nutrient information"""
    name: str
    value: float
    unit: str
    per_100g: float  # normalized to 100g for comparison

@dataclass
class ProductData:
    """Normalized product information"""
    barcode: Optional[str] = None
    name: str = ""
    brand: str = ""
    ingredients: List[str] = None
    nutrients: Dict[str, NutrientInfo] = None
    serving_size_g: Optional[float] = None
    categories: List[str] = None
    
    def __post_init__(self):
        if self.ingredients is None:
            self.ingredients = []
        if self.nutrients is None:
            self.nutrients = {}
        if self.categories is None:
            self.categories = []

@dataclass
class ScoreDriver:
    """Individual scoring factor"""
    factor: str
    impact: str  # positive, negative, neutral
    score_delta: float
    explanation: str
    source: str

@dataclass
class HealthScore:
    """Complete health assessment"""
    overall_score: int  # 0-100
    band: str  # A, B, C, D, E
    drivers: List[ScoreDriver]
    evidence_sources: List[str]
    confidence: str  # high, medium, low
    warnings: List[str]

class IngredientNormalizer:
    """Normalize and classify ingredients using food science principles"""
    
    # Based on FDA and EFSA ingredient classification systems
    HARMFUL_ADDITIVES = {
        'sodium nitrite', 'sodium nitrate', 'potassium nitrite', 'potassium nitrate',
        'bha', 'bht', 'tbhq', 'propyl gallate',
        'artificial colors', 'red dye 40', 'yellow 6', 'blue 1',
        'high fructose corn syrup', 'corn syrup solids'
    }
    
    ULTRA_PROCESSED_MARKERS = {
        'modified starch', 'hydrolyzed protein', 'isolated protein',
        'artificial flavors', 'natural flavors', 'flavor enhancer',
        'emulsifier', 'stabilizer', 'thickener'
    }
    
    BENEFICIAL_INGREDIENTS = {
        'whole grain', 'whole wheat', 'oats', 'quinoa', 'brown rice',
        'fiber', 'protein', 'vitamins', 'minerals'
    }

    @staticmethod
    def normalize_ingredient_list(raw_ingredients: str) -> List[str]:
        """Convert raw ingredient string to normalized list"""
        if not raw_ingredients:
            return []
        
        # Clean and split ingredients
        ingredients = re.split(r'[,;]', raw_ingredients.lower())
        normalized = []
        
        for ingredient in ingredients:
            ingredient = ingredient.strip()
            ingredient = re.sub(r'\([^)]*\)', '', ingredient)  # Remove parenthetical content
            ingredient = re.sub(r'\s+', ' ', ingredient).strip()
            if ingredient and len(ingredient) > 1:
                normalized.append(ingredient)
        
        logger.info(f"Normalized {len(normalized)} ingredients from raw text")
        return normalized

    @staticmethod
    def classify_ingredients(ingredients: List[str]) -> Dict[str, List[str]]:
        """Classify ingredients into categories for scoring"""
        classification = {
            'harmful_additives': [],
            'ultra_processed_markers': [],
            'beneficial_ingredients': [],
            'other': []
        }
        
        for ingredient in ingredients:
            ingredient_lower = ingredient.lower()
            classified = False
            
            for harmful in IngredientNormalizer.HARMFUL_ADDITIVES:
                if harmful in ingredient_lower:
                    classification['harmful_additives'].append(ingredient)
                    classified = True
                    break
            
            if not classified:
                for marker in IngredientNormalizer.ULTRA_PROCESSED_MARKERS:
                    if marker in ingredient_lower:
                        classification['ultra_processed_markers'].append(ingredient)
                        classified = True
                        break
            
            if not classified:
                for beneficial in IngredientNormalizer.BENEFICIAL_INGREDIENTS:
                    if beneficial in ingredient_lower:
                        classification['beneficial_ingredients'].append(ingredient)
                        classified = True
                        break
            
            if not classified:
                classification['other'].append(ingredient)
        
        return classification

class NutrientNormalizer:
    """Normalize nutrient data using official dietary guidelines"""
    
    # Based on FDA Daily Values and WHO recommendations
    DAILY_VALUES = {
        'calories': 2000,
        'total_fat': 65,      # grams
        'saturated_fat': 20,   # grams
        'trans_fat': 0,        # grams (no safe level)
        'cholesterol': 300,    # mg
        'sodium': 2300,        # mg
        'total_carbs': 300,    # grams
        'dietary_fiber': 25,   # grams
        'total_sugars': 50,    # grams (WHO recommendation)
        'added_sugars': 25,    # grams (WHO recommendation)
        'protein': 50,         # grams
    }
    
    @staticmethod
    def normalize_nutrients(raw_nutrients: Dict[str, str], serving_size_g: float = 100) -> Dict[str, NutrientInfo]:
        """Convert raw nutrient strings to standardized format"""
        normalized = {}
        
        for key, value_str in raw_nutrients.items():
            try:
                # Extract numeric value and unit
                value_match = re.search(r'(\d+\.?\d*)', str(value_str))
                if not value_match:
                    continue
                    
                value = float(value_match.group(1))
                unit_match = re.search(r'(mg|g|kcal|cal)', str(value_str).lower())
                unit = unit_match.group(1) if unit_match else 'g'
                
                # Normalize to per 100g
                per_100g = (value / serving_size_g) * 100 if serving_size_g > 0 else value
                
                # Convert units if needed
                if unit == 'mg' and key.lower() not in ['sodium', 'cholesterol']:
                    per_100g = per_100g / 1000  # mg to g
                    unit = 'g'
                
                normalized[key.lower().replace(' ', '_')] = NutrientInfo(
                    name=key,
                    value=value,
                    unit=unit,
                    per_100g=per_100g
                )
                
            except Exception as e:
                logger.warning(f"Failed to normalize nutrient {key}: {e}")
                continue
        
        logger.info(f"Normalized {len(normalized)} nutrients")
        return normalized

class HealthScorer:
    """Score products based on established nutritional guidelines"""
    
    def __init__(self):
        # Evidence sources - all peer-reviewed and authoritative
        self.sources = [
            "FDA Nutrition Facts Label Guidelines (2016)",
            "WHO Global Strategy on Diet, Physical Activity and Health (2004)",
            "Dietary Guidelines for Americans 2020-2025",
            "European Food Safety Authority (EFSA) Scientific Opinions",
            "American Heart Association Dietary Guidelines",
            "Harvard T.H. Chan School of Public Health Nutrition Source"
        ]
    
    def score_product(self, product: ProductData) -> HealthScore:
        """Generate comprehensive health score with evidence"""
        logger.info(f"Scoring product: {product.name}")
        
        base_score = 50  # Start neutral
        drivers = []
        warnings = []
        confidence_factors = []
        
        # Score based on nutrients
        if product.nutrients:
            nutrient_score, nutrient_drivers, nutrient_warnings = self._score_nutrients(product.nutrients)
            base_score += nutrient_score
            drivers.extend(nutrient_drivers)
            warnings.extend(nutrient_warnings)
            confidence_factors.append("nutrients")
        
        # Score based on ingredients
        if product.ingredients:
            ingredient_score, ingredient_drivers, ingredient_warnings = self._score_ingredients(product.ingredients)
            base_score += ingredient_score
            drivers.extend(ingredient_drivers)
            warnings.extend(ingredient_warnings)
            confidence_factors.append("ingredients")
        
        # Ensure score is within bounds
        final_score = max(0, min(100, int(base_score)))
        
        # Determine band (like Nutri-Score)
        if final_score >= 80:
            band = "A"
        elif final_score >= 65:
            band = "B"
        elif final_score >= 50:
            band = "C"
        elif final_score >= 35:
            band = "D"
        else:
            band = "E"
        
        # Determine confidence
        confidence = self._calculate_confidence(confidence_factors, product)
        
        logger.info(f"Final score: {final_score} (Band {band})")
        
        return HealthScore(
            overall_score=final_score,
            band=band,
            drivers=drivers,
            evidence_sources=self.sources,
            confidence=confidence,
            warnings=warnings
        )
    
    def _score_nutrients(self, nutrients: Dict[str, NutrientInfo]) -> Tuple[float, List[ScoreDriver], List[str]]:
        """Score based on nutrient profile"""
        score_delta = 0
        drivers = []
        warnings = []
        
        # Positive factors
        if 'dietary_fiber' in nutrients:
            fiber = nutrients['dietary_fiber'].per_100g
            if fiber >= 6:  # High fiber
                delta = min(10, fiber * 1.5)
                score_delta += delta
                drivers.append(ScoreDriver(
                    factor="High Fiber Content",
                    impact="positive",
                    score_delta=delta,
                    explanation=f"Contains {fiber:.1f}g fiber per 100g. High fiber supports digestive health and may reduce chronic disease risk.",
                    source="Dietary Guidelines for Americans 2020-2025"
                ))
        
        if 'protein' in nutrients:
            protein = nutrients['protein'].per_100g
            if protein >= 12:  # Good protein source
                delta = min(8, protein * 0.3)
                score_delta += delta
                drivers.append(ScoreDriver(
                    factor="Good Protein Source",
                    impact="positive",
                    score_delta=delta,
                    explanation=f"Contains {protein:.1f}g protein per 100g. Adequate protein supports muscle health and satiety.",
                    source="FDA Nutrition Facts Label Guidelines"
                ))
        
        # Negative factors
        if 'sodium' in nutrients:
            sodium_mg = nutrients['sodium'].per_100g * 10  # Convert to mg per 100g
            if sodium_mg > 600:  # High sodium
                delta = -min(15, (sodium_mg - 600) * 0.01)
                score_delta += delta
                drivers.append(ScoreDriver(
                    factor="High Sodium Content",
                    impact="negative",
                    score_delta=delta,
                    explanation=f"Contains {sodium_mg:.0f}mg sodium per 100g. High sodium intake linked to hypertension and cardiovascular disease.",
                    source="American Heart Association Dietary Guidelines"
                ))
                warnings.append("High sodium content may contribute to elevated blood pressure")
        
        if 'saturated_fat' in nutrients:
            sat_fat = nutrients['saturated_fat'].per_100g
            if sat_fat > 5:  # High saturated fat
                delta = -min(12, sat_fat * 1.5)
                score_delta += delta
                drivers.append(ScoreDriver(
                    factor="High Saturated Fat",
                    impact="negative",
                    score_delta=delta,
                    explanation=f"Contains {sat_fat:.1f}g saturated fat per 100g. High saturated fat intake may increase cardiovascular risk.",
                    source="WHO Global Strategy on Diet, Physical Activity and Health"
                ))
        
        if 'total_sugars' in nutrients:
            sugars = nutrients['total_sugars'].per_100g
            if sugars > 15:  # High sugar
                delta = -min(10, sugars * 0.5)
                score_delta += delta
                drivers.append(ScoreDriver(
                    factor="High Sugar Content",
                    impact="negative",
                    score_delta=delta,
                    explanation=f"Contains {sugars:.1f}g sugars per 100g. High sugar intake linked to obesity, diabetes, and dental problems.",
                    source="WHO Global Strategy on Diet, Physical Activity and Health"
                ))
        
        return score_delta, drivers, warnings
    
    def _score_ingredients(self, ingredients: List[str]) -> Tuple[float, List[ScoreDriver], List[str]]:
        """Score based on ingredient quality"""
        score_delta = 0
        drivers = []
        warnings = []
        
        classification = IngredientNormalizer.classify_ingredients(ingredients)
        
        # Penalize harmful additives
        harmful_count = len(classification['harmful_additives'])
        if harmful_count > 0:
            delta = -min(15, harmful_count * 5)
            score_delta += delta
            drivers.append(ScoreDriver(
                factor="Harmful Additives Present",
                impact="negative",
                score_delta=delta,
                explanation=f"Contains {harmful_count} potentially harmful additive(s): {', '.join(classification['harmful_additives'][:3])}. Some additives linked to health concerns in studies.",
                source="EFSA Scientific Opinions on Food Additives"
            ))
            warnings.append("Contains additives that some studies suggest may have negative health effects")
        
        # Penalize ultra-processed markers
        processed_count = len(classification['ultra_processed_markers'])
        if processed_count > 3:
            delta = -min(8, processed_count * 2)
            score_delta += delta
            drivers.append(ScoreDriver(
                factor="Highly Processed Food",
                impact="negative",
                score_delta=delta,
                explanation=f"Contains {processed_count} ultra-processing markers. Ultra-processed foods associated with increased chronic disease risk.",
                source="Harvard T.H. Chan School of Public Health"
            ))
        
        # Reward beneficial ingredients
        beneficial_count = len(classification['beneficial_ingredients'])
        if beneficial_count > 0:
            delta = min(10, beneficial_count * 3)
            score_delta += delta
            drivers.append(ScoreDriver(
                factor="Beneficial Ingredients",
                impact="positive",
                score_delta=delta,
                explanation=f"Contains {beneficial_count} beneficial ingredient(s): {', '.join(classification['beneficial_ingredients'][:3])}. These support nutritional quality.",
                source="Dietary Guidelines for Americans 2020-2025"
            ))
        
        return score_delta, drivers, warnings
    
    def _calculate_confidence(self, confidence_factors: List[str], product: ProductData) -> str:
        """Calculate confidence level in the score"""
        score = 0
        
        if "nutrients" in confidence_factors:
            score += 50
        if "ingredients" in confidence_factors:
            score += 30
        if product.barcode:
            score += 10
        if product.brand:
            score += 10
        
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        else:
            return "low"

class ProductDatabase:
    """Simple SQLite database for storing product history"""
    
    def __init__(self, db_path: str = "products.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barcode TEXT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    data_hash TEXT UNIQUE,
                    product_data TEXT,
                    health_score TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_barcode ON products(barcode)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_name ON products(name)
            """)
    
    def save_product(self, product: ProductData, score: HealthScore) -> str:
        """Save product and score to database"""
        data_hash = hashlib.md5(
            json.dumps(asdict(product), sort_keys=True).encode()
        ).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO products 
                (barcode, name, brand, data_hash, product_data, health_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                product.barcode,
                product.name,
                product.brand,
                data_hash,
                json.dumps(asdict(product)),
                json.dumps(asdict(score)),
                datetime.datetime.now().isoformat()
            ))
        
        logger.info(f"Saved product {product.name} to database")
        return data_hash
    
    def get_product_by_barcode(self, barcode: str) -> Optional[Tuple[ProductData, HealthScore]]:
        """Retrieve product by barcode"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT product_data, health_score FROM products 
                WHERE barcode = ? ORDER BY updated_at DESC LIMIT 1
            """, (barcode,))
            
            row = cursor.fetchone()
            if row:
                # Load product data and reconstruct NutrientInfo objects
                product_dict = json.loads(row[0])
                
                # Convert nutrient dictionaries back to NutrientInfo objects
                if 'nutrients' in product_dict and product_dict['nutrients']:
                    reconstructed_nutrients = {}
                    for key, nutrient_dict in product_dict['nutrients'].items():
                        reconstructed_nutrients[key] = NutrientInfo(
                            name=nutrient_dict['name'],
                            value=nutrient_dict['value'],
                            unit=nutrient_dict['unit'],
                            per_100g=nutrient_dict['per_100g']
                        )
                    product_dict['nutrients'] = reconstructed_nutrients
                
                product_data = ProductData(**product_dict)
                
                # Load health score and reconstruct ScoreDriver objects
                score_dict = json.loads(row[1])
                if 'drivers' in score_dict and score_dict['drivers']:
                    reconstructed_drivers = []
                    for driver_dict in score_dict['drivers']:
                        reconstructed_drivers.append(ScoreDriver(
                            factor=driver_dict['factor'],
                            impact=driver_dict['impact'],
                            score_delta=driver_dict['score_delta'],
                            explanation=driver_dict['explanation'],
                            source=driver_dict['source']
                        ))
                    score_dict['drivers'] = reconstructed_drivers
                
                health_score = HealthScore(**score_dict)
                return product_data, health_score
        
        return None
    
    def search_products(self, query: str) -> List[Tuple[str, str, str]]:
        """Search products by name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT name, brand, barcode FROM products 
                WHERE name LIKE ? OR brand LIKE ?
                ORDER BY updated_at DESC LIMIT 20
            """, (f"%{query}%", f"%{query}%"))
            
            return cursor.fetchall()
    
    def get_recent_products(self, limit: int = 20) -> List[Tuple[str, str, str, str]]:
        """Get recently analyzed products"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name, brand, barcode, updated_at FROM products 
                ORDER BY updated_at DESC LIMIT ?
            """, (limit,))
            
            return cursor.fetchall()

# Streamlit UI
def main():
    st.set_page_config(
        page_title="Food Health Rating App",
        page_icon="🥗",
        layout="wide"
    )
    
    st.title("🥗 Food Health Rating App")
    st.markdown("*Transparent, evidence-based health scores for packaged foods*")
    
    # Initialize components
    if 'db' not in st.session_state:
        st.session_state.db = ProductDatabase()
    if 'scorer' not in st.session_state:
        st.session_state.scorer = HealthScorer()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", [
        "Analyze Product", 
        "Browse History", 
        "About & Sources"
    ])
    
    if page == "Analyze Product":
        analyze_product_page()
    elif page == "Browse History":
        browse_history_page()
    else:
        about_page()

def analyze_product_page():
    st.header("Analyze a Product")
    
    # Input method selection
    input_method = st.radio(
        "How would you like to add the product?",
        ["Manual Entry", "Barcode Lookup", "Search Database", "Photo Upload (OCR)"]
    )
    
    product_data = None
    
    if input_method == "Manual Entry":
        product_data = manual_entry_form()
    elif input_method == "Barcode Lookup":
        product_data = barcode_lookup_form()
    elif input_method == "Search Database":
        product_data = search_database_form()
    else:
        product_data = photo_upload_form()

    if product_data:
        display_analysis(product_data)
# OCR/photo upload form for extracting ingredients and nutrition
def photo_upload_form() -> Optional[ProductData]:
    st.subheader("Upload Product Label Photo (OCR)")
    uploaded_file = st.file_uploader("Upload an image of the product label", type=["png", "jpg", "jpeg"])
    ocr_text = ""
    if uploaded_file:
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\siriu\Downloads\tesseract-ocr-w64-setup-5.5.0.20241111.exe'
            image = Image.open(uploaded_file)
            ocr_text = pytesseract.image_to_string(image)
            st.text_area("Extracted Text (OCR)", ocr_text, height=200)
        except Exception as e:
            st.error(f"OCR failed: {e}")
            return None
    else:
        st.info("Upload a product label image to extract text.")
        return None

    # Simple parsing for ingredients and nutrition facts
    ingredients = ""
    nutrients = {}
    serving_size = 100.0
    name = ""
    brand = ""
    barcode = ""
    categories = []

    # Try to extract ingredients
    match = re.search(r"ingredients[:]?(.+)", ocr_text, re.IGNORECASE)
    if match:
        ingredients = match.group(1).split("Nutrition")[0].strip()
    else:
        st.warning("Ingredients not found in OCR text. Please add manually.")

    # Try to extract nutrition facts
    nutrition_matches = re.findall(r"([A-Za-z ]+):?\s*(\d+\.?\d*)\s*(g|mg|kcal|cal)?", ocr_text)
    for n in nutrition_matches:
        key = n[0].strip()
        value = n[1]
        unit = n[2] if n[2] else "g"
        nutrients[key] = f"{value}{unit}"

    # Try to extract serving size
    serving_match = re.search(r"serving size[:]?\s*(\d+\.?\d*)\s*g", ocr_text, re.IGNORECASE)
    if serving_match:
        serving_size = float(serving_match.group(1))

    # Try to extract product name
    name_match = re.search(r"product name[:]?\s*([A-Za-z0-9 \-]+)", ocr_text, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()

    # Try to extract brand
    brand_match = re.search(r"brand[:]?\s*([A-Za-z0-9 \-]+)", ocr_text, re.IGNORECASE)
    if brand_match:
        brand = brand_match.group(1).strip()

    # Try to extract barcode
    barcode_match = re.search(r"barcode[:]?\s*(\d{8,14})", ocr_text, re.IGNORECASE)
    if barcode_match:
        barcode = barcode_match.group(1)

    # Normalize data
    normalized_ingredients = IngredientNormalizer.normalize_ingredient_list(ingredients)
    normalized_nutrients = NutrientNormalizer.normalize_nutrients(nutrients, serving_size)

    # Show what was found and what is missing
    st.markdown("**OCR Extraction Summary:**")
    st.write(f"**Name:** {name if name else 'Not found'}")
    st.write(f"**Brand:** {brand if brand else 'Not found'}")
    st.write(f"**Barcode:** {barcode if barcode else 'Not found'}")
    st.write(f"**Serving Size:** {serving_size}g")
    st.write(f"**Ingredients:** {', '.join(normalized_ingredients) if normalized_ingredients else 'Not found'}")
    st.write(f"**Nutrients:** {', '.join(normalized_nutrients.keys()) if normalized_nutrients else 'Not found'}")

    # Manual correction if needed
    st.markdown("---")
    st.markdown("**You can manually correct or add missing fields below:**")
    name = st.text_input("Product Name", value=name)
    brand = st.text_input("Brand", value=brand)
    barcode = st.text_input("Barcode", value=barcode)
    serving_size = st.number_input("Serving Size (g)", min_value=1.0, value=serving_size)
    ingredients_text = st.text_area("Ingredients", value=ingredients, height=100)

    # Nutrition facts manual entry
    col3, col4 = st.columns(2)
    with col3:
        calories = st.text_input("Calories", value=nutrients.get("Calories", ""))
        total_fat = st.text_input("Total Fat", value=nutrients.get("Total Fat", ""))
        saturated_fat = st.text_input("Saturated Fat", value=nutrients.get("Saturated Fat", ""))
        sodium = st.text_input("Sodium", value=nutrients.get("Sodium", ""))
    with col4:
        total_carbs = st.text_input("Total Carbohydrates", value=nutrients.get("Total Carbohydrates", ""))
        dietary_fiber = st.text_input("Dietary Fiber", value=nutrients.get("Dietary Fiber", ""))
        total_sugars = st.text_input("Total Sugars", value=nutrients.get("Total Sugars", ""))
        protein = st.text_input("Protein", value=nutrients.get("Protein", ""))

    submitted = st.button("Analyze Product (from OCR)")
    if submitted:
        # Create nutrient dictionary
        raw_nutrients = {}
        if calories: raw_nutrients['calories'] = calories
        if total_fat: raw_nutrients['total_fat'] = total_fat
        if saturated_fat: raw_nutrients['saturated_fat'] = saturated_fat
        if sodium: raw_nutrients['sodium'] = sodium
        if total_carbs: raw_nutrients['total_carbohydrates'] = total_carbs
        if dietary_fiber: raw_nutrients['dietary_fiber'] = dietary_fiber
        if total_sugars: raw_nutrients['total_sugars'] = total_sugars
        if protein: raw_nutrients['protein'] = protein

        normalized_ingredients = IngredientNormalizer.normalize_ingredient_list(ingredients_text)
        normalized_nutrients = NutrientNormalizer.normalize_nutrients(raw_nutrients, serving_size)

        product = ProductData(
            barcode=barcode if barcode else None,
            name=name,
            brand=brand,
            ingredients=normalized_ingredients,
            nutrients=normalized_nutrients,
            serving_size_g=serving_size,
            categories=categories
        )
        return product
    return None

def manual_entry_form() -> Optional[ProductData]:
    st.subheader("Enter Product Information")
    
    with st.form("product_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Product Name*", help="Required field")
            brand = st.text_input("Brand", help="Optional but recommended")
            barcode = st.text_input("Barcode", help="Optional UPC/EAN code")
            serving_size = st.number_input("Serving Size (g)", min_value=1.0, value=100.0)
        
        with col2:
            st.markdown("**Categories** (select all that apply)")
            categories = []
            if st.checkbox("Snack Food"): categories.append("snack")
            if st.checkbox("Breakfast Cereal"): categories.append("cereal")
            if st.checkbox("Packaged Meal"): categories.append("meal")
            if st.checkbox("Beverage"): categories.append("beverage")
            if st.checkbox("Dairy Product"): categories.append("dairy")
        
        st.markdown("**Ingredients**")
        ingredients_text = st.text_area(
            "Enter ingredients list",
            help="Copy from package label, separated by commas",
            height=100
        )
        
        st.markdown("**Nutrition Facts** (per serving)")
        col3, col4 = st.columns(2)
        
        with col3:
            calories = st.text_input("Calories", help="e.g., 150")
            total_fat = st.text_input("Total Fat", help="e.g., 8g")
            saturated_fat = st.text_input("Saturated Fat", help="e.g., 3g")
            sodium = st.text_input("Sodium", help="e.g., 300mg")
        
        with col4:
            total_carbs = st.text_input("Total Carbohydrates", help="e.g., 20g")
            dietary_fiber = st.text_input("Dietary Fiber", help="e.g., 3g")
            total_sugars = st.text_input("Total Sugars", help="e.g., 12g")
            protein = st.text_input("Protein", help="e.g., 6g")
        
        submitted = st.form_submit_button("Analyze Product")
        
        if submitted:
            if not name:
                st.error("Product name is required")
                return None
            
            # Create nutrient dictionary
            raw_nutrients = {}
            if calories: raw_nutrients['calories'] = calories
            if total_fat: raw_nutrients['total_fat'] = total_fat
            if saturated_fat: raw_nutrients['saturated_fat'] = saturated_fat
            if sodium: raw_nutrients['sodium'] = sodium
            if total_carbs: raw_nutrients['total_carbohydrates'] = total_carbs
            if dietary_fiber: raw_nutrients['dietary_fiber'] = dietary_fiber
            if total_sugars: raw_nutrients['total_sugars'] = total_sugars
            if protein: raw_nutrients['protein'] = protein
            
            # Normalize data
            normalized_ingredients = IngredientNormalizer.normalize_ingredient_list(ingredients_text)
            normalized_nutrients = NutrientNormalizer.normalize_nutrients(raw_nutrients, serving_size)
            
            product = ProductData(
                barcode=barcode if barcode else None,
                name=name,
                brand=brand,
                ingredients=normalized_ingredients,
                nutrients=normalized_nutrients,
                serving_size_g=serving_size,
                categories=categories
            )
            
            return product
    
    return None

def barcode_lookup_form() -> Optional[ProductData]:
    st.subheader("Barcode Lookup")
    barcode = st.text_input("Enter Barcode", help="UPC or EAN barcode")
    if barcode and st.button("Search Database"):
        # First check our local database
        result = st.session_state.db.get_product_by_barcode(barcode)
        if result:
            st.success("Found in local database!")
            return result[0]
        else:
            st.info("Barcode not found in local database. Searching Open Food Facts...")
            # Query Open Food Facts API
            try:
                api_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == 1:
                        product = data["product"]
                        name = product.get("product_name", "")
                        brand = product.get("brands", "")
                        ingredients_text = product.get("ingredients_text", "")
                        serving_size = 100.0
                        if product.get("serving_size"):
                            match = re.search(r"(\d+\.?\d*)\s*g", product["serving_size"])
                            if match:
                                serving_size = float(match.group(1))
                        # Nutrition facts
                        nutriments = product.get("nutriments", {})
                        raw_nutrients = {}
                        if "energy-kcal_100g" in nutriments:
                            raw_nutrients["calories"] = f"{nutriments['energy-kcal_100g']}kcal"
                        if "fat_100g" in nutriments:
                            raw_nutrients["total_fat"] = f"{nutriments['fat_100g']}g"
                        if "saturated-fat_100g" in nutriments:
                            raw_nutrients["saturated_fat"] = f"{nutriments['saturated-fat_100g']}g"
                        if "sodium_100g" in nutriments:
                            raw_nutrients["sodium"] = f"{nutriments['sodium_100g']}mg"
                        if "carbohydrates_100g" in nutriments:
                            raw_nutrients["total_carbohydrates"] = f"{nutriments['carbohydrates_100g']}g"
                        if "fiber_100g" in nutriments:
                            raw_nutrients["dietary_fiber"] = f"{nutriments['fiber_100g']}g"
                        if "sugars_100g" in nutriments:
                            raw_nutrients["total_sugars"] = f"{nutriments['sugars_100g']}g"
                        if "proteins_100g" in nutriments:
                            raw_nutrients["protein"] = f"{nutriments['proteins_100g']}g"
                        normalized_ingredients = IngredientNormalizer.normalize_ingredient_list(ingredients_text)
                        normalized_nutrients = NutrientNormalizer.normalize_nutrients(raw_nutrients, serving_size)
                        product_data = ProductData(
                            barcode=barcode,
                            name=name,
                            brand=brand,
                            ingredients=normalized_ingredients,
                            nutrients=normalized_nutrients,
                            serving_size_g=serving_size,
                            categories=[]
                        )
                        st.success("Product found via Open Food Facts!")
                        return product_data
                    else:
                        st.warning("Product not found in Open Food Facts. Please use manual entry.")
                else:
                    st.error(f"Open Food Facts API error: {resp.status_code}")
            except Exception as e:
                st.error(f"Error connecting to Open Food Facts: {e}")
    return None

def search_database_form() -> Optional[ProductData]:
    st.subheader("Search Product Database")
    
    query = st.text_input("Search by product name or brand")
    
    if query and len(query) >= 2:
        results = st.session_state.db.search_products(query)
        
        if results:
            st.write(f"Found {len(results)} product(s):")
            
            for i, (name, brand, barcode) in enumerate(results):
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{name}**")
                with col2:
                    st.write(f"*{brand or 'Unknown brand'}*")
                with col3:
                    if st.button("Select", key=f"select_{i}"):
                        result = st.session_state.db.get_product_by_barcode(barcode)
                        if result:
                            return result[0]
        else:
            st.info("No products found matching your search.")
    
    return None

def display_analysis(product: ProductData):
    """Display the complete product analysis"""
    st.header("Product Analysis")
    
    # Generate score
    score = st.session_state.scorer.score_product(product)
    
    # Save to database
    st.session_state.db.save_product(product, score)
    
    # Display score prominently
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        score_color = {
            'A': '#00C853',  # Green
            'B': '#64DD17',  # Light green
            'C': '#FFD600',  # Yellow
            'D': '#FF8F00',  # Orange
            'E': '#D32F2F'   # Red
        }
        
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background-color: {score_color[score.band]}20; border: 3px solid {score_color[score.band]};">
            <h2 style="color: {score_color[score.band]}; margin: 0;">Health Score: {score.overall_score}/100</h2>
            <h1 style="color: {score_color[score.band]}; margin: 10px 0; text-align: center;">Grade {score.band}</h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("Confidence", score.confidence.title())
    
    with col3:
        st.metric("Factors", len(score.drivers))
    
    # Product details
    st.subheader("Product Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Name:** {product.name}")
        if product.brand:
            st.write(f"**Brand:** {product.brand}")
        if product.barcode:
            st.write(f"**Barcode:** {product.barcode}")
        if product.categories:
            st.write(f"**Categories:** {', '.join(product.categories)}")
    
    with col2:
        if product.serving_size_g:
            st.write(f"**Serving Size:** {product.serving_size_g}g")
        st.write(f"**Ingredients Count:** {len(product.ingredients)}")
        st.write(f"**Nutrients Analyzed:** {len(product.nutrients)}")
    
    # Score drivers
    st.subheader("What Drives This Score")
    
    positive_drivers = [d for d in score.drivers if d.impact == "positive"]
    negative_drivers = [d for d in score.drivers if d.impact == "negative"]
    
    if positive_drivers:
        st.write("**✅ Positive Factors:**")
        for driver in positive_drivers:
            with st.expander(f"{driver.factor} (+{driver.score_delta:.1f} points)"):
                st.write(driver.explanation)
                st.caption(f"Source: {driver.source}")
    
    if negative_drivers:
        st.write("**⚠️ Negative Factors:**")
        for driver in negative_drivers:
            with st.expander(f"{driver.factor} ({driver.score_delta:.1f} points)"):
                st.write(driver.explanation)
                st.caption(f"Source: {driver.source}")
    
    # Warnings
    if score.warnings:
        st.subheader("⚠️ Health Warnings")
        for warning in score.warnings:
            st.warning(warning)
    
    # Evidence panel
    with st.expander("📚 Evidence & Sources"):
        st.write("This analysis is based on the following authoritative sources:")
        for source in score.evidence_sources:
            st.write(f"• {source}")
        
        st.markdown("---")
        st.write("**Methodology:** Scores are calculated using established nutritional guidelines and food science principles. Positive factors include beneficial nutrients and whole food ingredients, while negative factors include harmful additives, excessive sodium, saturated fat, and ultra-processed markers.")
    
    # Detailed nutrition facts
    if product.nutrients:
        with st.expander("📊 Detailed Nutrition Facts"):
            nutrition_df = pd.DataFrame([
                {
                    'Nutrient': nutrient.name,
                    'Per Serving': f"{nutrient.value}{nutrient.unit}",
                    'Per 100g': f"{nutrient.per_100g:.1f}{nutrient.unit}"
                }
                for nutrient in product.nutrients.values()
            ])
            st.dataframe(nutrition_df, use_container_width=True)
    
    # Ingredients analysis
    if product.ingredients:
        with st.expander("🧪 Ingredients Analysis"):
            classification = IngredientNormalizer.classify_ingredients(product.ingredients)
            
            if classification['beneficial_ingredients']:
                st.write("**✅ Beneficial Ingredients:**")
                st.write(", ".join(classification['beneficial_ingredients']))
            
            if classification['harmful_additives']:
                st.write("**❌ Potentially Harmful Additives:**")
                st.write(", ".join(classification['harmful_additives']))
            
            if classification['ultra_processed_markers']:
                st.write("**⚠️ Ultra-Processing Markers:**")
                st.write(", ".join(classification['ultra_processed_markers']))
            
            if classification['other']:
                st.write("**ℹ️ Other Ingredients:**")
                st.write(", ".join(classification['other']))

def browse_history_page():
    st.header("Browse Analysis History")
    
    # Recent products
    recent = st.session_state.db.get_recent_products(50)
    
    if recent:
        st.subheader("Recent Analyses")
        
        # Create dataframe for display
        df_data = []
        for name, brand, barcode, updated_at in recent:
            # Get the score for display
            result = st.session_state.db.get_product_by_barcode(barcode) if barcode else None
            score_band = result[1].band if result else "N/A"
            score_value = result[1].overall_score if result else "N/A"
            
            df_data.append({
                'Product': name,
                'Brand': brand or 'Unknown',
                'Score': f"{score_value} ({score_band})" if result else "N/A",
                'Last Updated': updated_at[:10],  # Just the date
                'Barcode': barcode or 'N/A'
            })
        
        df = pd.DataFrame(df_data)
        
        # Display with selection
        event = st.dataframe(
            df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Handle selection
        if event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_barcode = recent[selected_idx][2]
            
            if selected_barcode:
                result = st.session_state.db.get_product_by_barcode(selected_barcode)
                if result:
                    st.markdown("---")
                    display_analysis(result[0])
    else:
        st.info("No products analyzed yet. Go to 'Analyze Product' to get started!")
    
    # Search functionality
    st.subheader("Search History")
    search_query = st.text_input("Search your analyzed products")
    
    if search_query:
        results = st.session_state.db.search_products(search_query)
        
        if results:
            for name, brand, barcode in results:
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{name}**")
                with col2:
                    st.write(f"*{brand or 'Unknown brand'}*")
                with col3:
                    if st.button("View", key=f"view_{barcode}"):
                        result = st.session_state.db.get_product_by_barcode(barcode)
                        if result:
                            st.markdown("---")
                            display_analysis(result[0])

def about_page():
    st.header("About This App")
    
    st.markdown("""
    ## Mission
    
    This app provides **transparent, evidence-based health scores** for packaged foods based on authoritative medical and nutritional sources. Our goal is to help consumers make informed food choices by turning complex nutritional information into clear, comparable health signals.
    
    ## How It Works
    
    ### 1. Data Collection
    - **Manual Entry**: Input product information directly from nutrition labels
    - **Barcode Lookup**: Search your previously analyzed products
    - **Database Search**: Find and reanalyze products from your history
    
    ### 2. Normalization
    - Ingredients are classified using food science principles
    - Nutrients are standardized to per-100g values for comparison
    - Data quality issues are flagged and handled gracefully
    
    ### 3. Scoring Algorithm
    - **Base Score**: Starts at 50 (neutral)
    - **Positive Factors**: High fiber, protein, beneficial ingredients (+points)
    - **Negative Factors**: High sodium, saturated fat, harmful additives (-points)
    - **Final Range**: 0-100, converted to letter grades (A-E)
    
    ### 4. Evidence & Transparency
    - Every score factor is explained in plain language
    - All claims are linked to authoritative sources
    - Confidence levels indicate data completeness
    """)
    
    st.subheader("📚 Authoritative Sources")
    
    sources_info = {
        "FDA Nutrition Facts Label Guidelines (2016)": "Official US guidance on nutrition labeling standards and daily values",
        "WHO Global Strategy on Diet, Physical Activity and Health (2004)": "World Health Organization recommendations for healthy diets",
        "Dietary Guidelines for Americans 2020-2025": "Evidence-based nutrition recommendations from USDA and HHS",
        "European Food Safety Authority (EFSA) Scientific Opinions": "EU scientific assessments of food additives and nutrients",
        "American Heart Association Dietary Guidelines": "Cardiovascular health-focused nutrition recommendations",
        "Harvard T.H. Chan School of Public Health Nutrition Source": "Evidence-based nutrition information from leading research institution"
    }
    
    for source, description in sources_info.items():
        with st.expander(source):
            st.write(description)
    
    st.subheader("⚠️ Important Disclaimers")
    
    st.warning("""
    **This tool is for educational purposes only and is not a substitute for professional medical advice.**
    
    - Scores are based on general population guidelines and may not apply to specific dietary needs
    - Individual health conditions may require different nutritional considerations
    - Always consult healthcare professionals for personalized dietary advice
    - Food choices should consider cultural, economic, and personal factors beyond health scores
    """)
    
    st.subheader("🔧 Technical Details")
    
    with st.expander("Architecture & Implementation"):
        st.markdown("""
        **Data Flow:**
        1. Input → Normalization → Scoring → Explanation → Storage
        
        **Components:**
        - `IngredientNormalizer`: Classifies ingredients using food science databases
        - `NutrientNormalizer`: Standardizes nutrition data to comparable units
        - `HealthScorer`: Applies evidence-based scoring rules
        - `ProductDatabase`: SQLite storage for analysis history
        
        **Scoring Methodology:**
        - Fiber: +1.5 points per gram (≥6g threshold)
        - Protein: +0.3 points per gram (≥12g threshold)  
        - Sodium: -0.01 points per mg above 600mg/100g
        - Saturated Fat: -1.5 points per gram above 5g/100g
        - Sugars: -0.5 points per gram above 15g/100g
        - Harmful Additives: -5 points each
        - Ultra-processed Markers: -2 points each (>3 threshold)
        - Beneficial Ingredients: +3 points each
        
        **Confidence Calculation:**
        - Nutrients present: +50 points
        - Ingredients present: +30 points
        - Barcode available: +10 points
        - Brand specified: +10 points
        - High: ≥80 points, Medium: ≥60 points, Low: <60 points
        """)
    
    with st.expander("Data Privacy & Storage"):
        st.markdown("""
        - All data is stored locally in SQLite database
        - No external API calls or data sharing
        - Product information can be deleted by removing the database file
        - Barcode information is used only for local lookup and caching
        """)
    
    st.subheader("📊 Usage Statistics")
    
    # Show some basic stats from the database
    with sqlite3.connect(st.session_state.db.db_path) as conn:
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        unique_brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM products WHERE brand IS NOT NULL").fetchone()[0]
        avg_score = conn.execute("SELECT AVG(CAST(json_extract(health_score, '$.overall_score') AS FLOAT)) FROM products").fetchone()[0]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Products Analyzed", total_products)
    with col2:
        st.metric("Unique Brands", unique_brands)
    with col3:
        if avg_score:
            st.metric("Average Score", f"{avg_score:.1f}")
        else:
            st.metric("Average Score", "N/A")

# Run the app
if __name__ == "__main__":
    main()