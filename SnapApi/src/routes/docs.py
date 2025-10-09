from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import os
import yaml
import markdown
from pathlib import Path
from typing import Dict, List, Any
import re

router = APIRouter()

# Base directory for documentation
DOCS_BASE_DIR = "/app/docs"

def parse_jekyll_config() -> Dict[str, Any]:
    """Parse the Jekyll _config.yml file to extract navigation structure."""
    config_path = os.path.join(DOCS_BASE_DIR, "_config.yml")
    
    if not os.path.exists(config_path):
        return {"navigation": []}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Error parsing Jekyll config: {e}")
        return {"navigation": []}

def get_doc_content(filename: str) -> str:
    """Get the content of a documentation file."""
    # Remove .md extension if present
    if filename.endswith('.md'):
        filename = filename[:-3]
    
    # Try different possible paths
    possible_paths = [
        os.path.join(DOCS_BASE_DIR, f"{filename}.md"),
        os.path.join(DOCS_BASE_DIR, f"{filename}.markdown"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Remove Jekyll front matter if present
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                
                return content
            except Exception as e:
                print(f"Error reading file {path}: {e}")
                continue
    
    return f"Documentation file '{filename}' not found."

def convert_markdown_to_html(content: str) -> str:
    """Convert markdown content to HTML."""
    try:
        # Configure markdown with extensions
        md = markdown.Markdown(
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.toc',
                'markdown.extensions.codehilite',
                'markdown.extensions.footnotes',
                'markdown.extensions.attr_list',
                'markdown.extensions.def_list',
                'markdown.extensions.abbr',
                'markdown.extensions.footnotes',
                'markdown.extensions.md_in_html',
            ],
            extension_configs={
                'markdown.extensions.codehilite': {
                    'css_class': 'highlight'
                }
            }
        )
        
        html = md.convert(content)
        return html
    except Exception as e:
        print(f"Error converting markdown to HTML: {e}")
        return f"<p>Error converting markdown content: {str(e)}</p>"

def build_navigation_tree(navigation_config: List[Dict]) -> List[Dict]:
    """Build a navigation tree from Jekyll config."""
    navigation_tree = []
    
    for item in navigation_config:
        if 'children' in item:
            # This is a parent category
            children = []
            for child in item['children']:
                child_item = {
                    'title': child['title'],
                    'url': child['url'],
                    'filename': child['url'].lstrip('/') if child['url'] else None,
                    'type': 'document'
                }
                children.append(child_item)
            
            navigation_tree.append({
                'title': item['title'],
                'type': 'category',
                'children': children
            })
        else:
            # This is a direct document
            navigation_tree.append({
                'title': item['title'],
                'url': item.get('url', ''),
                'filename': item['url'].lstrip('/') if item.get('url') else None,
                'type': 'document'
            })
    
    return navigation_tree

@router.get("/navigation")
async def get_docs_navigation():
    """Get the documentation navigation structure."""
    try:
        config = parse_jekyll_config()
        navigation_config = config.get('navigation', [])
        navigation_tree = build_navigation_tree(navigation_config)
        
        return {
            "success": True,
            "navigation": navigation_tree,
            "title": config.get('title', 'SNAP Documentation'),
            "description": config.get('description', 'Comprehensive documentation for SNAP container checkpointing platform')
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/content/{filename}")
async def get_doc_content_endpoint(filename: str):
    """Get the content of a specific documentation file."""
    try:
        content = get_doc_content(filename)
        html_content = convert_markdown_to_html(content)
        
        return {
            "success": True,
            "content": html_content,
            "filename": filename
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/list")
async def list_docs():
    """List all available documentation files."""
    try:
        docs_list = []
        
        if os.path.exists(DOCS_BASE_DIR):
            for file in os.listdir(DOCS_BASE_DIR):
                if file.endswith('.md') and not file.startswith('_'):
                    filename = file[:-3]  # Remove .md extension
                    docs_list.append({
                        'filename': filename,
                        'title': filename.replace('-', ' ').title(),
                        'url': f"/{filename}"
                    })
        
        return {
            "success": True,
            "docs": docs_list
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/search")
async def search_docs(query: str):
    """Search through documentation content."""
    try:
        results = []
        
        if os.path.exists(DOCS_BASE_DIR):
            for file in os.listdir(DOCS_BASE_DIR):
                if file.endswith('.md') and not file.startswith('_'):
                    file_path = os.path.join(DOCS_BASE_DIR, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Remove front matter
                        if content.startswith('---'):
                            parts = content.split('---', 2)
                            if len(parts) >= 3:
                                content = parts[2].strip()
                        
                        # Simple text search (case insensitive)
                        if query.lower() in content.lower():
                            filename = file[:-3]
                            results.append({
                                'filename': filename,
                                'title': filename.replace('-', ' ').title(),
                                'url': f"/{filename}",
                                'snippet': content[:200] + "..." if len(content) > 200 else content
                            })
                    except Exception as e:
                        print(f"Error reading file {file}: {e}")
                        continue
        
        return {
            "success": True,
            "results": results,
            "query": query
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
