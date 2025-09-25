import base64
import copy


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def replace_image_url(messages, throw_details=False, keep_path=False):
    new_messages = copy.deepcopy(messages)
    for message in new_messages:
        if message["role"] == "user":
            for content in message["content"]:
                if isinstance(content, str):
                    continue
                if content["type"] == "image_url":
                    image_url = content["image_url"]["url"]
                    image_url_parts = image_url.split(";base64,")
                    if not keep_path:
                        content["image_url"]["url"] = image_url_parts[0] + ";base64," + image_to_base64(
                            image_url_parts[1])
                    else:
                        content["image_url"]["url"] = f"file://{image_url_parts[1]}"
                    if throw_details:
                        content["image_url"].pop("detail", None)
    return new_messages

def clean_tree_structure(text):
    lines = text.split('\n')
    cleaned_lines = []
    
    # Keep the first two header lines as is
    cleaned_lines.extend(lines[:2])
    
    # Process the remaining lines
    for line in lines[2:]:
        if not line.strip():
            continue
            
        parts = line.split(';')
        if len(parts) >= 4:
            # Keep component type, actions, empty text, and coordinates
            cleaned_line = f"{parts[0]};{parts[1]};;{parts[-1]}"
            cleaned_lines.append(cleaned_line)
            
    return '\n'.join(cleaned_lines)