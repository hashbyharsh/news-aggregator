import difflib
import re
import uuid
from typing import Set, List, Dict, Optional, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class NewsArticleSimilarity:
    """
    A comprehensive similarity calculator for news articles with multiple algorithms
    optimized for automotive news content deduplication.
    """
    
    def __init__(self):
        # Common stop words to filter out for better similarity matching
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
            'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its',
            'our', 'their', 'said', 'says', 'new', 'latest', 'breaking', 'news'
        }
        
        # Enhanced Indian car brands and models for entity matching
        self.car_brands = {
            "maruti": ["swift", "alto", "wagon r", "baleno", "vitara brezza", "dzire", "ertiga", "ciaz", "s-cross", "xl6", "celerio", "ignis", "fronx", "jimny"],
            "maruti suzuki": ["swift", "alto", "wagon r", "baleno", "vitara brezza", "dzire", "ertiga", "ciaz", "s-cross", "xl6", "celerio", "ignis", "fronx", "jimny"],
            "hyundai": ["i20", "creta", "verna", "venue", "grand i10", "santro", "tucson", "kona", "elantra", "sonata", "alcazar", "aura"],
            "tata": ["nexon", "harrier", "safari", "tigor", "tiago", "punch", "altroz", "bolt", "zest", "hexa", "curvv"],
            "mahindra": ["xuv700", "xuv300", "scorpio", "thar", "bolero", "marazzo", "alturas", "kuv100", "xuv500", "scorpio n", "xuv400"],
            "honda": ["city", "amaze", "jazz", "wr-v", "civic", "cr-v", "pilot", "accord", "elevate"],
            "toyota": ["innova", "fortuner", "etios", "corolla", "camry", "yaris", "glanza", "urban cruiser", "hyryder", "hilux"],
            "ford": ["ecosport", "figo", "aspire", "freestyle", "endeavour", "mustang"],
            "kia": ["seltos", "sonet", "carnival", "carens", "ev6"],
            "mg": ["hector", "zs ev", "gloster", "astor", "comet"],
            "volkswagen": ["polo", "vento", "ameo", "tiguan", "t-roc", "passat", "virtus", "taigun"],
            "skoda": ["rapid", "superb", "octavia", "kodiaq", "kushaq", "slavia"],
            "renault": ["kwid", "duster", "captur", "triber", "kiger"],
            "nissan": ["magnite", "kicks", "terrano", "micra", "sunny", "x-trail"],
            "citroen": ["c5 aircross", "c3", "ec3", "c3 aircross"],
            "jeep": ["compass", "wrangler", "grand cherokee", "meridian"],
            "tvs": ["ntorq", "jupiter", "apache", "raider", "ronin", "iqube", "creon", "orbiter"],
            "hero": ["splendor", "passion", "hf deluxe", "glamour", "xtreme", "xoom"],
            "bajaj": ["pulsar", "avenger", "dominar", "platina", "ct", "chetak"],
            "royal enfield": ["classic", "bullet", "thunderbird", "himalayan", "interceptor", "continental gt", "meteor", "hunter"],
            "yamaha": ["fz", "mt", "r15", "fascino", "ray zr", "aerox"],
            "ktm": ["duke", "rc", "adventure"],
            "bmw": ["3 series", "5 series", "7 series", "x1", "x3", "x5", "x7", "z4", "i4", "ix"],
            "mercedes": ["a-class", "c-class", "e-class", "s-class", "gla", "glb", "glc", "gle", "gls", "eqc", "eqs"],
            "audi": ["a3", "a4", "a6", "a8", "q2", "q3", "q5", "q7", "q8", "tt", "r8", "e-tron"],
            "jaguar": ["xe", "xf", "xj", "f-pace", "e-pace", "i-pace"],
            "land rover": ["discovery", "range rover", "defender", "freelander", "evoque"],
            "porsche": ["911", "cayenne", "macan", "panamera", "boxster", "cayman", "taycan"],
            "tesla": ["model s", "model 3", "model x", "model y", "cybertruck"]
        }
    
    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for better similarity matching"""
        if not text:
            return ""
        
        text = text.lower()
        
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        noise_patterns = [
            r'\b(breaking|latest|update|news|report|article|story)\b',
            r'\b(according to|sources say|reports suggest)\b',
            r'\b(today|yesterday|recently|currently)\b'
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, ' ', text)
        
        return text.strip()
    
    def get_meaningful_words(self, text: str) -> Set[str]:
        """Extract meaningful words excluding stop words and short words"""
        processed_text = self.preprocess_text(text)
        words = processed_text.split()
        
        meaningful_words = {
            word for word in words 
            if word not in self.stop_words and len(word) > 2
        }
        
        return meaningful_words
    
    def title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between titles using difflib (most accurate for titles)"""
        if not title1 or not title2:
            return 0.0
        

        clean_title1 = self.preprocess_text(title1)
        clean_title2 = self.preprocess_text(title2)
        
        # Use difflib for sequence matching
        similarity = difflib.SequenceMatcher(None, clean_title1, clean_title2).ratio()
        
        words1 = self.get_meaningful_words(clean_title1)
        words2 = self.get_meaningful_words(clean_title2)
        
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
            # Weighted combination: 70% sequence similarity + 30% word overlap
            similarity = 0.7 * similarity + 0.3 * word_overlap
        
        return similarity
    
    def content_similarity(self, content1: str, content2: str) -> float:
        """Calculate content similarity using TF-IDF like approach"""
        if not content1 or not content2:
            return 0.0
        
        words1 = self.get_meaningful_words(content1)
        words2 = self.get_meaningful_words(content2)
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity for word sets
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Word frequency similarity for important terms
        counter1 = Counter(content1.lower().split())
        counter2 = Counter(content2.lower().split())
        
        common_words = set(counter1.keys()).intersection(set(counter2.keys()))
        freq_similarity = 0.0
        
        if common_words:
            freq_diffs = []
            for word in common_words:
                if word not in self.stop_words and len(word) > 2:
                    freq1 = counter1[word]
                    freq2 = counter2[word]
                    # Normalized frequency difference
                    freq_diffs.append(1 - abs(freq1 - freq2) / max(freq1, freq2))
            
            if freq_diffs:
                freq_similarity = sum(freq_diffs) / len(freq_diffs)
        
        return 0.8 * jaccard + 0.2 * freq_similarity
    
    def extract_car_entities(self, text: str) -> Tuple[Set[str], Set[str]]:
        """Extract car brands and models from text"""
        text_lower = text.lower()
        found_brands = set()
        found_models = set()
        
        for brand, models in self.car_brands.items():
            if f" {brand} " in f" {text_lower} " or text_lower.startswith(brand + " ") or text_lower.endswith(" " + brand):
                found_brands.add(brand)
                
                for model in models:
                    if f" {model} " in f" {text_lower} " or text_lower.startswith(model + " ") or text_lower.endswith(" " + model):
                        found_models.add(model)
        
        return found_brands, found_models
    
    def car_entity_similarity(self, text1: str, text2: str) -> float:
        """Check if articles mention the same car brands/models"""
        brands1, models1 = self.extract_car_entities(text1)
        brands2, models2 = self.extract_car_entities(text2)
        
        brand_overlap = len(brands1.intersection(brands2))
        model_overlap = len(models1.intersection(models2))
        
        if brand_overlap > 0 or model_overlap > 0:
            total_brands = max(len(brands1), len(brands2), 1)
            total_models = max(len(models1), len(models2), 1)
            brand_sim = brand_overlap / total_brands
            model_sim = model_overlap / total_models
            return min(1.0, (brand_sim * 0.6 + model_sim * 0.4))
        
        return 0.0
    
    def calculate_similarity(self, article1: Dict, article2: Dict) -> float:
        """
        Calculate overall similarity between two articles
        
        Args:
            article1: Dictionary with 'title' and 'content' keys
            article2: Dictionary with 'title' and 'content' keys
        
        Returns:
            float: Similarity score between 0.0 and 1.0
        """
        try:
            title1 = article1.get('title', '')
            title2 = article2.get('title', '')
            content1 = article1.get('content', '')
            content2 = article2.get('content', '')
            
            if not title1 or not title2:
                return 0.0
            
            # Calculate different similarity components
            title_sim = self.title_similarity(title1, title2)
            content_sim = self.content_similarity(content1, content2)
            entity_sim = self.car_entity_similarity(f"{title1} {content1}", f"{title2} {content2}")
            
            # Weighted combination - titles are most important for news deduplication
            # Title: 60%, Content: 30%, Entities: 10%
            overall_similarity = (0.6 * title_sim + 
                                0.3 * content_sim + 
                                0.1 * entity_sim)
            
            logger.debug(f"Similarity between '{title1[:30]}...' and '{title2[:30]}...': "
                        f"Title={title_sim:.2f}, Content={content_sim:.2f}, "
                        f"Entity={entity_sim:.2f}, Overall={overall_similarity:.2f}")
            
            return overall_similarity
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def group_similar_articles(self, articles: List[Dict], similarity_threshold: float = 0.65) -> Dict[str, List[Dict]]:
        """
        Group similar articles together
        
        Args:
            articles: List of article dictionaries with 'title' and 'content' keys
            similarity_threshold: Minimum similarity to group articles (0.65 is good for news)
            
        Returns:
            dict: Groups of similar articles with group_id as keys
        """
        groups = {}
        
        for article in articles:
            matched_group = None
            max_similarity = 0.0
            
            for group_id, group in groups.items():
                representative = group[0]
                similarity = self.calculate_similarity(article, representative)
                
                if similarity > similarity_threshold and similarity > max_similarity:
                    matched_group = group_id
                    max_similarity = similarity
            
            if matched_group:
                groups[matched_group].append(article)
                logger.debug(f"Added article to existing group {matched_group} "
                           f"with similarity {max_similarity:.2f}")
            else:
                new_group_id = str(uuid.uuid4())
                groups[new_group_id] = [article]
                logger.debug(f"Created new group {new_group_id} for article")
        
        return groups


# =================================
# LEGACY COMPATIBILITY FUNCTIONS
# =================================

_similarity_calculator = NewsArticleSimilarity()

def string_similarity(str1: str, str2: str) -> float:
    """
    Legacy function using difflib for backward compatibility
    """
    return difflib.SequenceMatcher(None, str1, str2).ratio()

def cosine_similarity_score(text1: str, text2: str) -> float:
    """
    Simple cosine similarity implementation for text
    """
    try:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        return len(intersection) / (len(words1) * len(words2)) ** 0.5
    except Exception as e:
        logger.error(f"Error in cosine similarity: {e}")
        return 0.0

def enhanced_string_similarity(article1_data: str, article2_data: str) -> float:
    """
    Enhanced similarity function to replace your current string_similarity
    This function expects combined title + content strings and uses the enhanced calculator
    """
    parts1 = article1_data.split()
    parts2 = article2_data.split()
    
    article1 = {
        'title': ' '.join(parts1[:20]) if len(parts1) > 0 else '',
        'content': ' '.join(parts1[20:]) if len(parts1) > 20 else ' '.join(parts1)
    }
    
    article2 = {
        'title': ' '.join(parts2[:20]) if len(parts2) > 0 else '', 
        'content': ' '.join(parts2[20:]) if len(parts2) > 20 else ' '.join(parts2)
    }
    
    return _similarity_calculator.calculate_similarity(article1, article2)

def calculate_article_similarity(article1: Dict, article2: Dict, similarity_threshold: float = 0.65) -> float:
    """
    Calculate similarity between two article dictionaries
    
    Args:
        article1: Dict with 'title' and 'content' keys
        article2: Dict with 'title' and 'content' keys
        similarity_threshold: Not used in calculation but kept for API compatibility
    
    Returns:
        float: Similarity score between 0.0 and 1.0
    """
    return _similarity_calculator.calculate_similarity(article1, article2)

def group_articles_by_similarity(articles: List[Dict], similarity_threshold: float = 0.65) -> Dict[str, List[Dict]]:
    """
    Group articles by similarity
    
    Args:
        articles: List of article dicts with 'title' and 'content' keys
        similarity_threshold: Minimum similarity to group articles
    
    Returns:
        dict: Groups of similar articles with group_id as keys
    """
    return _similarity_calculator.group_similar_articles(articles, similarity_threshold)

def extract_car_brand_model(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract car brand and model from text - legacy function for backward compatibility
    
    Returns:
        tuple: (brand_name, model_name) or (None, None) if not found
    """
    brands, models = _similarity_calculator.extract_car_entities(text)
    
    brand_name = next(iter(brands), None)
    model_name = next(iter(models), None)
    
    if brand_name:
        brand_name = brand_name.title()
    if model_name:
        model_name = model_name.title()
    
    return brand_name, model_name