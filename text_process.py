# text_processor.py
import torch

# Process text and extract features
def process_text(text, models):
    tokenizer = models['text_tokenizer']
    model = models['text_model']
    
    # Preprocess text
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128)
    
    # Get features
    with torch.no_grad():
        outputs = model(**inputs)
        
    # Get CLS token embedding as text representation
    embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()
    
    # Simple keyword-based category detection
    category_keywords = {
        'pothole': ['pothole', 'hole', 'crater', 'road damage'],
        'garbage': ['garbage', 'trash', 'waste', 'litter', 'dump'],
        'streetlight': ['streetlight', 'light', 'lamp', 'lighting', 'pole'],
        'graffiti': ['graffiti', 'paint', 'vandalism', 'drawing', 'spray'],
        'flooding': ['flood', 'water', 'puddle', 'drain', 'clogged'],
        'sidewalk_damage': ['sidewalk', 'pavement', 'crack', 'broken', 'uneven']
    }
    
    # Default category
    category = 'unknown'
    max_count = 0
    
    # Simple keyword matching
    text_lower = text.lower()
    for cat, keywords in category_keywords.items():
        count = sum(1 for keyword in keywords if keyword in text_lower)
        if count > max_count:
            max_count = count
            category = cat
    
    return {
        'embedding': embedding,
        'category': category
    }
