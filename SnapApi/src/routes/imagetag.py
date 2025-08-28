from fastapi import APIRouter, HTTPException
from classes.imagetag import generate_image_tag, parse_image_tag, get_image_component, ImageTagComponents

router = APIRouter()

# Image Tag Routes

@router.post("/generate")
async def generate_image_tag_endpoint(request: ImageTagComponents):
    """
    Generate an image tag from individual components.
    Returns format: <registry>/<repo>/<cluster>-<namespace>-<app>:<origImageShortDigest>-<PodTemplateHash>
    """
    try:
        image_tag = generate_image_tag(
            registry=request.registry,
            repo=request.repo,
            cluster=request.cluster,
            namespace=request.namespace,
            app=request.app,
            origImageShortDigest=request.origImageShortDigest,
            PodTemplateHash=request.PodTemplateHash
        )
        return {
            "success": True,
            "components": request.dict(),
            "generated_image_tag": image_tag
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid component values: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating image tag: {str(e)}")


@router.post("/parse")
async def parse_image_tag_endpoint(image_tag: str):
    """
    Parse an image tag and return all its components.
    Expected format: <registry>/<repo>/<cluster>-<namespace>-<app>:<origImageShortDigest>-<PodTemplateHash>
    """
    try:
        components = parse_image_tag(image_tag)
        return {
            "success": True,
            "image_tag": image_tag,
            "components": components
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image tag format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing image tag: {str(e)}")


@router.get("/component/{component}")
async def get_image_component_endpoint(component: str, image_tag: str):
    """
    Get a specific component from an image tag.
    Valid components: registry, repo, cluster, namespace, app, origImageShortDigest, PodTemplateHash
    """
    try:
        value = get_image_component(image_tag, component)
        return {
            "success": True,
            "image_tag": image_tag,
            "component": component,
            "value": value
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting component: {str(e)}")
