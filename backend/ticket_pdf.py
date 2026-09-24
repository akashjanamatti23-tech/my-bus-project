from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import qrcode
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

GREEN = colors.HexColor('#1B4D3E')
GREY = colors.HexColor('#71717A')
SAND = colors.HexColor('#F2EEDD')
FONT = 'GoBusVera'
pdfmetrics.registerFont(TTFont(FONT, str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))


def text(canvas, value, x, y, width=490, size=10, color=colors.black):
    paragraph = Paragraph(escape(str(value)), ParagraphStyle('ticket', fontName=FONT,
        fontSize=size, leading=size * 1.4, textColor=color))
    _, height = paragraph.wrap(width, 90)
    paragraph.drawOn(canvas, x, y - height)


def make_pdf(booking):
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4, pageCompression=1)
    canvas.setTitle(f"GoBus TEST ticket {booking['pnr']}")
    canvas.setAuthor('GoBus')
    width, height = A4
    for index, passenger in enumerate(booking['passengers']):
        canvas.setFillColor(GREEN)
        canvas.rect(0, height - 115, width, 115, fill=1, stroke=0)
        text(canvas, 'GoBus.', 38, height - 25, size=28, color=colors.white)
        text(canvas, 'YOUR JOURNEY, IN ONE PLACE', 39, height - 70, size=9, color=colors.white)
        text(canvas, booking['pnr'], 350, height - 35, width=205, size=12, color=colors.white)
        text(canvas, f"Traveller {index + 1} of {len(booking['passengers'])}", 350, height - 60, size=9, color=colors.white)
        canvas.setFillColor(SAND)
        canvas.roundRect(36, height - 156, width - 72, 29, 7, fill=1, stroke=0)
        text(canvas, 'TEST - NO MONEY CHARGED - NOT VALID FOR REAL TRAVEL', 48, height - 134, size=9, color=GREEN)
        text(canvas, f"{booking['route']['source']}  >  {booking['route']['destination']}", 38, height - 178, size=20, color=GREEN)
        departure = booking['departure_at'].astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %H:%M IST')
        arrival = booking['arrival_at'].astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %H:%M IST')
        text(canvas, f'Departure: {departure}  |  Arrival: {arrival}', 38, height - 216, size=9, color=GREY)
        text(canvas, passenger['name'], 38, height - 250, size=16)
        text(canvas, f"Age {passenger['age']} | {passenger['gender']} | Seat {passenger['seat_label']} | {passenger['deck']} deck | {passenger['seat_type']}", 38, height - 277, size=9)
        text(canvas, f"{booking['bus']['operator']} | {booking['bus']['name']} | {booking['bus']['number']}", 38, height - 300, size=10)
        text(canvas, f"Boarding: {booking['boarding_point']}", 38, height - 327, size=10)
        text(canvas, f"Dropping: {booking['dropping_point']}", 38, height - 356, size=10)
        for offset, key, label, hint in [(38, 'source_qr', '01  SOURCE / BOARDING', 'Outside scanner - future integration'),
                                        (315, 'destination_qr', '02  DESTINATION / EXIT', 'Inside scanner - future integration')]:
            text(canvas, label, offset, height - 403, width=240, size=10, color=GREEN)
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
            qr.add_data(passenger[key]['payload']); qr.make(fit=True)
            image = BytesIO(); qr.make_image(fill_color='black', back_color='white').save(image, format='PNG'); image.seek(0)
            canvas.drawImage(ImageReader(image), offset, height - 617, width=185, height=185, mask='auto')
            text(canvas, hint, offset, height - 626, width=230, size=8, color=GREY)
        text(canvas, f"Booking total: INR {booking['total']:,.2f}  |  Amount charged: INR 0.00", 38, height - 672, size=11)
        text(canvas, f"Base: INR {booking['base_fare']:,.2f} | Convenience fee: INR {booking['convenience_fee']:,.2f}", 38, height - 696, size=9, color=GREY)
        text(canvas, 'Keep these unique QR credentials private. GPS checks, scanners and door controls are not enabled in this release.', 38, height - 731, width=520, size=9, color=GREY)
        text(canvas, 'Test confirmation only. This ticket cannot open a physical door and is not evidence of a real payment.', 38, height - 764, width=520, size=9, color=GREY)
        text(canvas, f"Booking ID: {booking['id']}", 38, 31, size=7, color=GREY)
        canvas.showPage()
    canvas.save()
    return output.getvalue()