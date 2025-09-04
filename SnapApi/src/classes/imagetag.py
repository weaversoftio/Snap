from pydantic import BaseModel, validator
from typing import Optional
import re


class ImageTagComponents(BaseModel):
    """Model for individual components of an image tag"""
    registry: str
    repo: str
    cluster: str
    namespace: str
    app: str
    origImageShortDigest: str
    PodTemplateHash: str

    @validator('registry', 'repo', 'cluster', 'namespace', 'app', 'origImageShortDigest', 'PodTemplateHash')
    def validate_components(cls, v):
        """Validate components are non-empty strings"""
        if not v or not isinstance(v, str):
            raise ValueError("All components must be non-empty strings")
        
        return v.strip()



class ImageTagParser(BaseModel):
    """Parser class for generating and parsing image tags"""
    
    def __init__(self):
        super().__init__()
    
    def generate_tag(self, components: ImageTagComponents) -> str:
        """
        Generate image tag from components
        Format: <registry>/<repo>/<cluster>-<namespace>-<app>:<origImageShortDigest>-<PodTemplateHash>
        
        Args:
            components: ImageTagComponents object with all required fields
            
        Returns:
            str: Generated image tag
        """
        try:
            # Validate components
            components_dict = components.dict()
            
            # Build the tag according to the specified format
            # Convert repository portion to lowercase for Docker registry compatibility
            repo_path = f"{components.cluster}-{components.namespace}-{components.app}".lower()
            image_part = f"{components.registry}/{components.repo}/{repo_path}"
            tag_part = f"{components.origImageShortDigest}-{components.PodTemplateHash}"
            
            return f"{image_part}:{tag_part}"
            
        except Exception as e:
            raise ValueError(f"Error generating image tag: {str(e)}")
    
    def parse_tag(self, image_tag: str) -> ImageTagComponents:
        """
        Parse image tag back to components
        Format: <registry>/<repo>/<cluster>-<namespace>-<app>:<origImageShortDigest>-<PodTemplateHash>
        
        Args:
            image_tag: String in the expected format
            
        Returns:
            ImageTagComponents: Parsed components
            
        Raises:
            ValueError: If the tag format is invalid
        """
        try:
            if not image_tag or not isinstance(image_tag, str):
                raise ValueError("Image tag must be a non-empty string")
            
            # Find the last colon to separate image part from tag part
            # This handles registries with ports like "192.168.33.204:8082"
            colon_index = image_tag.rfind(':')
            if colon_index == -1:
                raise ValueError("Invalid image tag format: missing ':' separator")
            
            image_part = image_tag[:colon_index]
            tag_part = image_tag[colon_index + 1:]
            
            if not image_part or not tag_part:
                raise ValueError("Invalid image tag format: empty image or tag part")
            
            # Parse image part: <registry>/<repo>/<cluster>-<namespace>-<app>
            image_components = image_part.split('/')
            if len(image_components) < 3:
                raise ValueError("Invalid image part format: expected at least 3 components separated by '/'")
            
            # Handle case where registry might contain additional slashes (like docker.io/library)
            # We expect exactly 3 main components: registry, repo, cluster-namespace-app
            # The last component is cluster-namespace-app, second-to-last is repo, everything before is registry
            if len(image_components) == 3:
                registry, repo, cluster_namespace_app = image_components
            else:
                # If more than 3 components, assume registry might contain slashes
                cluster_namespace_app = image_components[-1]
                repo = image_components[-2]
                registry = '/'.join(image_components[:-2])
            
            # Parse cluster-namespace-app part: <cluster>-<namespace>-<app>
            # We need to be careful here as cluster, namespace, or app might contain hyphens
            # We'll assume app is the last component after splitting by '-'
            cluster_namespace_app_components = cluster_namespace_app.split('-')
            if len(cluster_namespace_app_components) < 3:
                raise ValueError("Invalid cluster-namespace-app format: expected at least 3 components separated by '-'")
            
            # The app is the last component, namespace is second-to-last, cluster is everything before
            app = cluster_namespace_app_components[-1]
            namespace = cluster_namespace_app_components[-2]
            cluster = '-'.join(cluster_namespace_app_components[:-2])
            
            # Parse tag part: <origImageShortDigest>-<PodTemplateHash>
            tag_components = tag_part.split('-')
            if len(tag_components) < 2:
                raise ValueError("Invalid tag part format: expected at least 2 components separated by '-'")
            
            # The PodTemplateHash is the last component, origImageShortDigest is everything before
            PodTemplateHash = tag_components[-1]
            origImageShortDigest = '-'.join(tag_components[:-1])
            
            # Create and return ImageTagComponents object
            return ImageTagComponents(
                registry=registry,
                repo=repo,
                cluster=cluster,
                namespace=namespace,
                app=app,
                origImageShortDigest=origImageShortDigest,
                PodTemplateHash=PodTemplateHash
            )
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Error parsing image tag: {str(e)}")
    
    def get_component(self, image_tag: str, component_name: str) -> str:
        """
        Get a specific component from an image tag
        
        Args:
            image_tag: String in the expected format
            component_name: Name of the component to extract
            
        Returns:
            str: Value of the requested component
            
        Raises:
            ValueError: If the tag format is invalid or component doesn't exist
        """
        valid_components = ['registry', 'repo', 'cluster', 'namespace', 'app', 'origImageShortDigest', 'PodTemplateHash']
        
        if component_name not in valid_components:
            raise ValueError(f"Invalid component name. Valid components are: {', '.join(valid_components)}")
        
        components = self.parse_tag(image_tag)
        return getattr(components, component_name)
    
    def to_dict(self, image_tag: str) -> dict:
        """
        Convert image tag to dictionary representation
        
        Args:
            image_tag: String in the expected format
            
        Returns:
            dict: Dictionary with all components
        """
        components = self.parse_tag(image_tag)
        return components.dict()


# Convenience functions for direct usage
def generate_image_tag(registry: str, repo: str, cluster: str, namespace: str, 
                      app: str, origImageShortDigest: str, PodTemplateHash: str) -> str:
    """
    Convenience function to generate image tag from individual parameters
    
    Returns:
        str: Generated image tag
    """
    components = ImageTagComponents(
        registry=registry,
        repo=repo,
        cluster=cluster,
        namespace=namespace,
        app=app,
        origImageShortDigest=origImageShortDigest,
        PodTemplateHash=PodTemplateHash
    )
    
    parser = ImageTagParser()
    return parser.generate_tag(components)


def parse_image_tag(image_tag: str) -> dict:
    """
    Convenience function to parse image tag and return as dictionary
    
    Args:
        image_tag: String in the expected format
        
    Returns:
        dict: Dictionary with all components
    """
    parser = ImageTagParser()
    return parser.to_dict(image_tag)


def get_image_component(image_tag: str, component_name: str) -> str:
    """
    Convenience function to get a specific component from image tag
    
    Args:
        image_tag: String in the expected format
        component_name: Name of the component to extract
        
    Returns:
        str: Value of the requested component
    """
    parser = ImageTagParser()
    return parser.get_component(image_tag, component_name)
