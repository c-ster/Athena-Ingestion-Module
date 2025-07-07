import os
import yake
from PyPDF2 import PdfReader
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

LANGUAGE = "english"
SENTENCES_COUNT = 5  # Number of sentences in the generated abstract

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

def generate_abstract(text):
    """Generates an abstract from the text, with checks for text length."""
    if not text or len(text.split()) < 50: # Check if text is too short
        print("Text content is too short to generate a meaningful abstract.")
        return "Not enough content to generate an abstract."
    try:
        parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
        stemmer = Stemmer(LANGUAGE)
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words(LANGUAGE)
        
        summary = summarizer(parser.document, SENTENCES_COUNT)
        abstract = " ".join(str(s) for s in summary)
        return abstract if abstract else "Abstract generation resulted in empty content."
    except Exception as e:
        print(f"Error generating abstract: {e}")
        return "Abstract could not be generated due to an error."

def generate_keywords(text):
    """Generates keywords from the text, with checks for text length."""
    if not text or len(text.split()) < 10: # Check if text is too short
        print("Text content is too short to generate keywords.")
        return []
    try:
        kw_extractor = yake.KeywordExtractor(lan=LANGUAGE.split('-')[0], n=1, dedupLim=0.9, top=10)
        keywords = kw_extractor.extract_keywords(text)
        return [kw for kw, score in keywords]
    except Exception as e:
        print(f"Error generating keywords: {e}")
        return []

def process_file_metadata(file_path, file_ext, text_content):
    """Extracts and generates metadata for a given file, ensuring a rich output."""
    print(f"Processing metadata for {os.path.basename(file_path)}...")
    
    # 1. Start with metadata from the PDF, if applicable
    final_metadata = extract_metadata_from_pdf(file_path) if file_ext == '.pdf' else {}

    # 2. Always generate abstract and keywords from the full text
    print("Generating abstract from full text...")
    generated_abstract = generate_abstract(text_content)
    if generated_abstract and "could not be generated" not in generated_abstract:
        final_metadata['abstract'] = generated_abstract
    elif 'subject' in final_metadata:
        final_metadata['abstract'] = final_metadata.pop('subject') # Use subject if generation fails

    print("Generating keywords from full text...")
    generated_keywords = generate_keywords(text_content)
    if generated_keywords:
        final_metadata['keywords'] = generated_keywords

    # 3. Clean up final metadata dictionary
    # Remove keys with None or empty values for a cleaner output
    cleaned_metadata = {k: v for k, v in final_metadata.items() if v is not None and v != ""}

    print(f"Final metadata for {os.path.basename(file_path)}: {cleaned_metadata}")
    return cleaned_metadata
