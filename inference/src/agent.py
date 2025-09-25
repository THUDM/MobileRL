import base64
import math
from io import BytesIO
from typing import List, Dict, Any, Callable, Optional, Tuple

from PIL import Image
from agentrl.worker.task import Session
from agentrl.worker.typings import AgentCancelledException
from android_lab.agent import RLAgent
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionContentPartParam
from openai.types.chat.chat_completion_content_part_image_param import ImageURL


class AgentRLAgent(RLAgent):

    def __init__(self,
                 session: Session,
                 renew_callback: Optional[Callable[[], Any]] = None,
                 image_max_pixels: Optional[int] = None):
        super().__init__()
        self.name = 'AgentRLAgent'
        self.session = session
        self.session.set_full_history(True)
        self.renew_callback = renew_callback
        self.image_max_pixels = image_max_pixels

    def act(self, messages: List[Dict[str, Any]]) -> Tuple[bool, str]:
        if self.renew_callback:
            self.renew_callback()

        messages = self.format_messages(messages)
        messages = self._process_messages(messages)
        self.session.cover(messages)
        try:
            response = self.session.sync_action()
        except AgentCancelledException:
            return False, 'Cancelled'
        return True, response.messages[0]['content']

    def _process_messages(self, messages: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        result: List[ChatCompletionMessageParam] = []
        for message in messages:
            if 'content' in message and isinstance(message['content'], list):
                content: List[ChatCompletionContentPartParam] = []
                for item in message['content']:
                    if 'image_url' in item and 'url' in item['image_url']:
                        url = self._process_image_url(item['image_url']['url'])
                        item['image_url'] = ImageURL(
                            url=url,
                            detail='auto'
                        )
                    content.append(item)
                message['content'] = content
            result.append(message)
        return result

    def _process_image_url(self, image_url: str) -> str:
        # Strip the prefix and base64-decode
        if image_url.startswith("data:image"):
            if "," in image_url:
                _, img_b64 = image_url.split(",", 1)
            else:
                img_b64 = image_url
        else:
            img_b64 = image_url
        img_bytes = base64.b64decode(img_b64)

        # Open image as PIL.Image
        image = Image.open(BytesIO(img_bytes))

        # Optionally resize to max_pixels if specified
        if self.image_max_pixels is not None and self.image_max_pixels > 0:
            cur_pixels = image.width * image.height
            if cur_pixels > self.image_max_pixels:
                resize_factor = math.sqrt(self.image_max_pixels / cur_pixels)
                new_width = max(1, int(image.width * resize_factor))
                new_height = max(1, int(image.height * resize_factor))
                image = image.resize((new_width, new_height))

        # Convert to RGB for consistency
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Encode image as PNG in memory
        buf = BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"
