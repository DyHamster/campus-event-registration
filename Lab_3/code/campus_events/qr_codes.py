"""电子票二维码图片的生成和识别。"""

from pathlib import Path

from .tickets import TicketError


def save_qr(code: str, path: Path) -> None:
    """将票码保存为 PNG 二维码。"""
    image_module, zxing = _libraries()
    barcode = zxing.create_barcode(code, zxing.BarcodeFormat.QRCode)
    image = image_module.fromarray(barcode.to_image(scale=8))
    with path.open("xb") as output:
        image.save(output, format="PNG")


def read_qr(path: Path) -> str:
    """从 PNG 或 JPEG 读取一个二维码内容。"""
    image_module, zxing = _libraries()
    try:
        with image_module.open(path, formats=("PNG", "JPEG")) as image:
            barcodes = zxing.read_barcodes(
                image.convert("L"), formats=zxing.BarcodeFormat.QRCode
            )
    except (OSError, image_module.DecompressionBombError) as error:
        raise TicketError(f"无法读取二维码图片：{path}") from error
    if len(barcodes) != 1:
        raise TicketError("请提供只包含一个可识别二维码的图片。")
    return barcodes[0].text


def _libraries():
    try:
        import zxingcpp
        from PIL import Image
    except ImportError as error:
        raise TicketError(
            "使用二维码图片前，请运行 python3 -m pip install -r requirements.txt。"
        ) from error
    return Image, zxingcpp
