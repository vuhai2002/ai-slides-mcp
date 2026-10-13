"""Instructions appended to the prompt when a reference image is attached.

The attached image is always SEEN by the model; the mode decides what it should
do with it:
  "style"                              - borrow the LOOK only (palette, layout,
                                         typography); never copy its text/content.
                                         Used by styled_deck.
  "logo" / "asset"                     - the reference IS a real brand asset; place
                                         it into the image exactly as given.
  "render" / "restyle" / "architecture" - the reference is a 3D render of a real
                                         building; keep the architecture, change only
                                         materials, lighting and landscaping.
"""
from __future__ import annotations

_STYLE_SUFFIX = (
    " QUAN TRỌNG: Ảnh đính kèm CHỈ là tham chiếu PHONG CÁCH THIẾT KẾ "
    "(bảng màu, bố cục, kiểu chữ, không khí, hoạ tiết trang trí). TUYỆT ĐỐI "
    "KHÔNG sao chép chữ, tiêu đề, hay nội dung cụ thể trong ảnh tham chiếu. "
    "Hãy tạo slide MỚI với nội dung đã cho ở trên, mang phong cách giống ảnh "
    "tham chiếu. (IMPORTANT: the attached image is a DESIGN-STYLE reference "
    "ONLY - palette, layout, typography, mood, decorative motifs. Do NOT copy "
    "any text, titles, or specific content from it; create a NEW slide with "
    "the content above, styled like the reference.)"
)

_LOGO_SUFFIX = (
    " QUAN TRỌNG: Ảnh đính kèm là LOGO thương hiệu THẬT. Hãy đưa CHÍNH XÁC logo "
    "này vào ảnh - giữ nguyên chữ, màu sắc, hình dạng và tỉ lệ của logo; TUYỆT "
    "ĐỐI không vẽ lại, không đổi font, không bịa logo khác. Đặt logo gọn gàng, "
    "cân đối, không che nội dung chính. (IMPORTANT: the attached image is the "
    "REAL brand logo - incorporate it into the composition EXACTLY as given, "
    "preserving its exact text, colors, shape and proportions; do NOT redraw, "
    "restyle, or invent a different logo.)"
)

_RENDER_SUFFIX = (
    " QUAN TRỌNG: Ảnh đính kèm là ẢNH RENDER 3D của một công trình thật đã có bản vẽ. "
    "Hãy GIỮ NGUYÊN kiến trúc: hình khối, số tầng, chiều cao tầng, vị trí và kích thước "
    "cửa, ban công, mái, góc máy, tiêu cự và bố cục khung hình. Chỉ thay đổi vật liệu, "
    "màu sắc, ánh sáng, thời điểm trong ngày, cảnh quan, cây xanh và không khí theo phong "
    "cách mô tả ở trên. Không thêm tầng, không bớt cửa, không đổi hình dáng mái, không "
    "thêm chữ hay logo. (IMPORTANT: the attached image is a 3D RENDER of a real, already "
    "drawn building. Keep the architecture EXACTLY: massing, number of floors, floor "
    "heights, position and size of every opening, balconies, roof shape, camera angle, "
    "focal length and framing. Change ONLY materials, colors, lighting, time of day, "
    "landscaping and mood to match the style described above. Do not add or remove "
    "floors or openings, do not reshape the roof, do not add text or logos.)"
)

_LOGO_MODES = ("logo", "asset")
_RENDER_MODES = ("render", "restyle", "architecture")


def is_render_mode(ref_mode: str) -> bool:
    """True when the reference is a building render to restyle.

    Callers skip all prompt rewriting (LLM enhance and the offline slide
    template) in this mode, since both would turn the prompt into a slide.
    """
    return ref_mode in _RENDER_MODES


def ref_suffix(ref_mode: str) -> str:
    """Pick the reference-image instruction for the given mode (default: style)."""
    if is_render_mode(ref_mode):
        return _RENDER_SUFFIX
    if ref_mode in _LOGO_MODES:
        return _LOGO_SUFFIX
    return _STYLE_SUFFIX
