import os
import json
import openai
import yake
from typing import Dict, Any, List, Optional
from PyPDF2 import PdfReader
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
from translation import translate_text

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

LANGUAGE = "english"
SENTENCES_COUNT = 5  # Number of sentences in the generated abstract

# System prompts for OpenAI
ABSTRACT_SYSTEM_PROMPT = """You are a helpful assistant that generates concise and informative abstracts for documents. 
Generate a clear and concise abstract that summarizes the main points of the document. 
Focus on the key findings, methodology, and conclusions. Keep it professional and objective."""

KEYWORDS_SYSTEM_PROMPT = """You are a helpful assistant that extracts relevant keywords from documents. 
Generate a list of 5-10 keywords that best represent the main topics and concepts in the document. 
Use noun phrases and be specific. Format as a JSON array of strings."""

async def translate_metadata(metadata: Dict[str, Any], target_lang: str = 'en') -> Dict[str, Any]:
    """
    Translate metadata fields to the target language.
    
    Args:
        metadata: Dictionary containing metadata
        target_lang: Target language code (default: 'en' for English)
        
    Returns:
        Dict with translated metadata
    """
    if not metadata:
        return {}
        
    translated = {}
    for key, value in metadata.items():
        if not value:
            continue
            
        # Handle different field types
        if key in ['title', 'subject', 'abstract']:
            try:
                translated_value = await translate_text(str(value), target_lang=target_lang)
                translated[key] = translated_value
            except Exception as e:
                print(f"Error translating {key}: {e}")
                translated[key] = value  # Keep original if translation fails
                
        elif key == 'author':
            if isinstance(value, str):
                try:
                    # Try to translate author names (may not work well for all names)
                    translated_value = await translate_text(value, target_lang=target_lang)
                    translated[key] = translated_value
                except Exception as e:
                    print(f"Error translating author: {e}")
                    translated[key] = value
            else:
                translated[key] = value
                
        elif key == 'keywords':
            if isinstance(value, list):
                translated_keywords = []
                for kw in value:
                    try:
                        translated_kw = await translate_text(str(kw), target_lang=target_lang)
                        translated_keywords.append(translated_kw)
                    except Exception as e:
                        print(f"Error translating keyword {kw}: {e}")
                        translated_keywords.append(str(kw))
                translated[key] = translated_keywords
            else:
                translated[key] = value
        else:
            translated[key] = value
            
    return translated

def extract_metadata_from_pdf(file_path):
    """Extracts metadata from a PDF file."""
    metadata = {}
    try:
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            info = reader.metadata
            if info:
                metadata['title'] = info.title
                metadata['author'] = info.author
                metadata['subject'] = info.subject
                metadata['creator'] = info.creator
                metadata['producer'] = info.producer
                metadata['creation_date'] = info.creation_date.isoformat() if info.creation_date else None
                metadata['modification_date'] = info.modification_date.isoformat() if info.modification_date else None
    except Exception as e:
        print(f"Error extracting PDF metadata: {e}")
    return metadata

async def generate_abstract(text: str, min_words: int = 50) -> str:
    """
    Generates an abstract from the text using OpenAI's API.
    
    Args:
        text: The text to generate an abstract from
        min_words: Minimum number of words required to generate an abstract
        
    Returns:
        Generated abstract or a default message if text is too short or an error occurs
    """
    if not text or len(text.split()) < min_words:
        print("Text content is too short to generate a meaningful abstract.")
        return "No abstract available. The document content was insufficient to generate an abstract."
    
    # Initialize client with API key from environment
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        # Truncate text to fit within token limits while preserving context
        max_chars = 100000  # Conservative limit to stay within token limits
        truncated_text = text[:max_chars]
        
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": ABSTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate an abstract for the following document. Focus on the main points and key findings. If the text is in a non-English language, translate the abstract to English.\n\n{truncated_text}"}
            ],
            temperature=0.3,  # Lower temperature for more focused and deterministic output
            max_tokens=500,  # Limit abstract length
            timeout=30  # Timeout in seconds
        )
        
        abstract = response.choices[0].message.content.strip()
        if not abstract:
            raise ValueError("Empty response from OpenAI API")
            
        return abstract
        
    except Exception as e:
        print(f"Error generating abstract with OpenAI: {e}")
        # Fall back to the original method if OpenAI fails
        try:
            print("Falling back to Sumy for abstract generation...")
            parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
            stemmer = Stemmer(LANGUAGE)
            summarizer = LsaSummarizer(stemmer)
            summarizer.stop_words = get_stop_words(LANGUAGE)
            
            summary = summarizer(parser.document, SENTENCES_COUNT)
            abstract = " ".join(str(s) for s in summary)
            
            if not abstract:
                return "Abstract generation failed. The document content may be too short or in an unsupported format."
                
            return abstract
            
        except Exception as e2:
            print(f"Error with fallback abstract generation: {e2}")
            return "Abstract generation failed. The document content may be in an unsupported format or too short for analysis."
            return "Abstract could not be generated due to an error."

async def generate_keywords(text: str, min_words: int = 10) -> List[str]:
    """
    Generates keywords from the text using OpenAI's API.
    
    Args:
        text: The text to extract keywords from
        min_words: Minimum number of words required to generate keywords
        
    Returns:
        List of generated keywords
    """
    if not text or len(text.split()) < min_words:
        print("Text content is too short to generate keywords.")
        return []
    
    try:
        # Truncate text to fit within token limits
        max_chars = 50000  # Conservative limit for keyword extraction
        truncated_text = text[:max_chars]
        
        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": KEYWORDS_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract 5-10 keywords from the following text. Focus on the main topics, concepts, and entities. Return a JSON object with a single key 'keywords' containing an array of strings.\n\n{truncated_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,  # Lower temperature for more consistent results
            max_tokens=200,   # Should be enough for 5-10 keywords
            timeout=20        # Timeout in seconds
        )
        
        # Parse the response as JSON and extract keywords
        try:
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")
                
            # Try to parse the response as JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract keywords from plain text
                print(f"Warning: Expected JSON but got plain text: {content}")
                # Extract potential keywords from the text (simple heuristic)
                keywords = [kw.strip('"\'') for kw in content.split(',') if kw.strip()]
                keywords = list(set(k.lower() for k in keywords if len(k) > 2))  # Filter out very short words
                return keywords[:10]  # Return max 10 keywords
            
            # Handle different JSON response formats
            if isinstance(result, dict):
                # Try common keys that might contain keywords
                for key in ['keywords', 'key_words', 'key_phrases', 'tags', 'terms']:
                    if key in result and isinstance(result[key], list):
                        keywords = result[key]
                        break
                else:
                    # If no specific key found, use all string values
                    keywords = [v for v in result.values() if isinstance(v, str)]
            elif isinstance(result, list):
                keywords = result
            else:
                keywords = []
            
            # Ensure we have a list of strings
            if isinstance(keywords, list):
                # Clean and deduplicate keywords
                cleaned_keywords = []
                for k in keywords:
                    if isinstance(k, str):
                        cleaned_keywords.append(k.strip().lower())
                    elif isinstance(k, (int, float, bool)):
                        cleaned_keywords.append(str(k).lower())
                
                # Remove empty strings and duplicates
                cleaned_keywords = list(set(k for k in cleaned_keywords if k.strip()))
                return cleaned_keywords[:10]  # Return max 10 keywords
                
            return []
            
            
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"Error parsing keywords JSON: {e}")
            # Fall through to fallback method
            
        # Fall back to the original method if OpenAI response parsing fails
        kw_extractor = yake.KeywordExtractor(
            lan=LANGUAGE.split('-')[0], 
            n=1, 
            dedupLim=0.9, 
            top=10,
            features=None
        )
        keywords = kw_extractor.extract_keywords(text)
        return [kw for kw, score in sorted(keywords, key=lambda x: x[1])][:10]  # Sort by score and take top 10
        
    except Exception as e:
        print(f"Error generating keywords with OpenAI, falling back to YAKE: {e}")
        try:
            kw_extractor = yake.KeywordExtractor(
                lan=LANGUAGE.split('-')[0], 
                n=1, 
                dedupLim=0.9, 
                top=10,
                features=None
            )
            keywords = kw_extractor.extract_keywords(text)
            return [kw for kw, score in sorted(keywords, key=lambda x: x[1])][:10]  # Sort by score and take top 10
        except Exception as e2:
            print(f"Error with fallback keyword extraction: {e2}")
            return []

async def process_file_metadata(file_path: str, file_ext: str, text_content: str) -> Dict[str, Any]:
    """
    Extracts, generates, and processes metadata for a given file.
    Ensures all metadata is in English and handles missing fields.
    
    Args:
        file_path: Path to the file
        file_ext: File extension (e.g., '.pdf')
        text_content: Extracted text content from the file
        
    Returns:
        Dictionary containing processed metadata
    """
    print(f"Processing metadata for {os.path.basename(file_path)}...")
    
    # 1. Start with metadata from the PDF, if applicable
    final_metadata = {}
    if file_ext.lower() == '.pdf':
        final_metadata = extract_metadata_from_pdf(file_path)
        
        # Translate PDF metadata to English
        if final_metadata:
            final_metadata = await translate_metadata(final_metadata, target_lang='en')
    
    # 2. Handle authors - ensure we have at least "No Authors"
    if not final_metadata.get('author') and not final_metadata.get('authors'):
        final_metadata['authors'] = ["No Authors"]
    
    # 3. Generate abstract if not present or empty
    if not final_metadata.get('abstract'):
        print("Generating abstract from full text...")
        try:
            final_metadata['abstract'] = await generate_abstract(text_content)
        except Exception as e:
            print(f"Error generating abstract: {e}")
            final_metadata['abstract'] = "Abstract could not be generated."
    
    # 4. Generate keywords if not present or empty
    if not final_metadata.get('keywords'):
        print("Generating keywords from full text...")
        try:
            keywords = await generate_keywords(text_content)
            # Ensure we have at least some keywords
            if not keywords and text_content.strip():
                # Fallback to YAKE if OpenAI fails
                kw_extractor = yake.KeywordExtractor(
                    lan=LANGUAGE.split('-')[0], 
                    n=1, 
                    dedupLim=0.9, 
                    top=10,
                    features=None
                )
                keywords = [kw for kw, _ in kw_extractor.extract_keywords(text_content)][:10]
            final_metadata['keywords'] = keywords if keywords else ["general"]
        except Exception as e:
            print(f"Error generating keywords: {e}")
            final_metadata['keywords'] = ["general"]
    
    # 5. Ensure all string fields are in English
    try:
        final_metadata = await translate_metadata(final_metadata, target_lang='en')
    except Exception as e:
        print(f"Error translating metadata: {e}")
        # Continue with untranslated metadata rather than failing
    
    # 6. Clean up final metadata dictionary
    cleaned_metadata = {}
    for k, v in final_metadata.items():
        if v is not None and v != "":
            # Convert single-item lists to single values for cleaner output
            if isinstance(v, list) and len(v) == 1 and k not in ['authors', 'keywords']:
                cleaned_metadata[k] = v[0]
            else:
                cleaned_metadata[k] = v
    
    # 7. Ensure required fields exist with sensible defaults
    if 'title' not in cleaned_metadata or not cleaned_metadata['title']:
        cleaned_metadata['title'] = os.path.splitext(os.path.basename(file_path))[0]
    
    # Ensure authors is always a list
    if 'authors' not in cleaned_metadata or not cleaned_metadata['authors']:
        cleaned_metadata['authors'] = ["No Authors"]
    elif isinstance(cleaned_metadata['authors'], str):
        cleaned_metadata['authors'] = [cleaned_metadata['authors']]
    
    # Ensure keywords is always a list
    if 'keywords' not in cleaned_metadata or not cleaned_metadata['keywords']:
        cleaned_metadata['keywords'] = ["general"]
    elif isinstance(cleaned_metadata['keywords'], str):
        cleaned_metadata['keywords'] = [cleaned_metadata['keywords']]
    
    print(f"Final metadata for {os.path.basename(file_path)}: {json.dumps(cleaned_metadata, indent=2, ensure_ascii=False)}")
    return cleaned_metadata
