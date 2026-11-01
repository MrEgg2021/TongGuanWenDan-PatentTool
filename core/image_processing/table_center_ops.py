from __future__ import annotations

import os

from PIL import Image


def pad_table_for_centering_keep_height(
    self,
    image_path,
    current_width_mm,
    current_height_mm,
    *,
    target_width_mm=None,
):
    if target_width_mm is None:
        return current_width_mm, current_height_mm

    try:
        current_width_value = float(current_width_mm)
        current_height_value = float(current_height_mm)
        target_width_value = float(target_width_mm)
    except (TypeError, ValueError):
        return current_width_mm, current_height_mm

    if current_width_value <= 0 or current_height_value <= 0 or target_width_value <= 0:
        return current_width_mm, current_height_mm
    if target_width_value <= current_width_value + 1e-6:
        return round(current_width_value, 2), round(current_height_value, 2)
    if not image_path or not os.path.isfile(image_path):
        return round(current_width_value, 2), round(current_height_value, 2)

    try:
        with Image.open(image_path) as img:
            try:
                src_fmt = str(getattr(img, 'format', '') or '').upper()
            except Exception:
                src_fmt = ''
            save_as_png = src_fmt == 'PNG' or str(image_path).lower().endswith('.png')
            img = img.convert('RGB')
            width_px, height_px = img.size
            if width_px <= 0 or height_px <= 0:
                return round(current_width_value, 2), round(current_height_value, 2)

            px_per_mm = float(width_px) / float(current_width_value)
            if px_per_mm <= 0:
                return round(current_width_value, 2), round(current_height_value, 2)

            target_width_px = max(int(width_px), int(round(float(target_width_value) * float(px_per_mm))))
            if target_width_px <= int(width_px):
                return round(current_width_value, 2), round(current_height_value, 2)

            canvas = Image.new('RGB', (int(target_width_px), int(height_px)), self.config.get('bg_color', '#FFFFFF'))
            offset_x = max(0, int((int(target_width_px) - int(width_px)) / 2))
            canvas.paste(img, (int(offset_x), 0))

            if save_as_png:
                canvas.save(image_path, format='PNG', dpi=(300, 300))
            else:
                canvas.save(
                    image_path,
                    quality=int(self.config.get('jpeg_quality', 95)),
                    subsampling=int(self.config.get('jpeg_subsampling', 0)),
                    dpi=(300, 300),
                )
    except Exception:
        return round(current_width_value, 2), round(current_height_value, 2)

    return round(float(target_width_value), 2), round(float(current_height_value), 2)


__all__ = ['pad_table_for_centering_keep_height']
