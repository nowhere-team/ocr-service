import io

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class PipelineAnimator:
    """creates animations from pipeline stages"""

    def create_slideshow_frames(
        self, stages: list[dict], storage_client, width: int = 800, add_labels: bool = True
    ) -> list[Image.Image]:
        """create frames for slideshow with optional labels"""
        images_data = []
        for stage in stages:
            image_key = stage.get("imageKey")
            if not image_key:
                continue
            img = storage_client.get_image(image_key)
            if not img:
                continue
            img = img.convert("RGB")
            images_data.append((img, stage))

        if not images_data:
            return []

        first_img = images_data[0][0]
        if first_img.width > width:
            ratio = width / first_img.width
            target_height = int(first_img.height * ratio)
        else:
            target_height = first_img.height

        frames = []
        for img, stage in images_data:
            if img.height != target_height:
                ratio = target_height / img.height
                new_width = int(img.width * ratio)
                img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)

            if img.width > width:
                ratio = width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((width, new_height), Image.Resampling.LANCZOS)

            canvas = Image.new("RGB", (width, target_height), (0, 0, 0))
            x_offset = (width - img.width) // 2
            y_offset = (target_height - img.height) // 2
            canvas.paste(img, (x_offset, y_offset))

            if add_labels:
                canvas = self._add_label(canvas, stage)

            frames.append(canvas)

        return frames

    @staticmethod
    def _add_label(img: Image.Image, stage: dict) -> Image.Image:
        """add text label to image"""
        draw = ImageDraw.Draw(img)
        step_name = stage.get("step", "unknown").replace("_", " ").title()
        description = stage.get("description", "")
        label_text = f"{step_name}"
        if description and len(description) < 80:
            label_text = f"{step_name}: {description}"

        # noinspection PyBroadException
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), label_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        padding = 15
        box_height = text_height + padding * 2

        draw.rectangle([(0, 0), (img.width, box_height)], fill=(0, 0, 0, 200))
        text_x = (img.width - text_width) // 2
        text_y = padding
        draw.text((text_x, text_y), label_text, fill=(255, 255, 255), font=font)

        return img

    @staticmethod
    def create_gif(
        frames: list[Image.Image], duration_per_frame: float = 1.0, loop: bool = True
    ) -> bytes:
        """create animated gif from frames"""
        if not frames:
            raise ValueError("no frames provided")

        output = io.BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=int(duration_per_frame * 1000),
            loop=0 if loop else 1,
            optimize=False,
        )
        output.seek(0)
        return output.getvalue()

    @staticmethod
    def create_mp4(
        frames: list[Image.Image],
        fps: float = 1.0,
    ) -> bytes:
        """create mp4 video from frames without audio"""
        if not frames:
            raise ValueError("no frames provided")

        frame_arrays = np.stack([np.array(frame) for frame in frames], axis=0)

        output = io.BytesIO()
        iio.imwrite(output, frame_arrays, extension=".mp4", fps=fps)

        output.seek(0)
        return output.getvalue()
