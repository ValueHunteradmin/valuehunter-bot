from PIL import Image, ImageDraw, ImageFont

BASE_IMAGE = "assets/valuehunter_base.png"

def get_font(size, bold=False):
    try:
        if bold:
            return ImageFont.truetype("Arial Bold.ttf", size)
        else:
            return ImageFont.truetype("Arial.ttf", size)
    except:
        return ImageFont.load_default()


def generate_ai_result_image(results):

    img = Image.open(BASE_IMAGE).convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_header = get_font(50, True)
    font_bet = get_font(40)
    font_title = get_font(60, True)
    font_score = get_font(50, True)

    # AI Header
    draw.text(
        (300,120),
        "AI SIGNAL ENGINE REPORT",
        fill=(255,215,0),
        font=font_header
    )

    y = 420
    wins = 0

    for i,(bet,result) in enumerate(results):

        if result == "WIN":
            text = f"⚽ Bet {i+1} — WIN ✅"
            wins += 1
        else:
            text = f"⚽ Bet {i+1} — LOST ❌"

        draw.text((220,y),text,(255,255,255),font=font_bet)

        y += 70

    total = len(results)

    if wins == total:
        title = "PERFECT DAY"
        subtitle = "+PROFIT"
        color = (0,255,120)

    elif wins >= 2:
        title = "PROFITABLE DAY"
        subtitle = "+PROFIT"
        color = (255,215,0)

    elif wins == 1:
        title = "BREAK EVEN"
        subtitle = "1 WON"
        color = (255,255,255)

    else:
        title = "TOUGH DAY"
        subtitle = "LOSS"
        color = (255,80,80)

    draw.text((350,680),title,color,font=font_title)

    score = f"{wins} / {total} WON"

    draw.text((420,760),score,(255,255,255),font=font_score)

    draw.text((470,830),subtitle,color,font=font_bet)

    path = "results.png"

    img.save(path)

    return path