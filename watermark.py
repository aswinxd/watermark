import os
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from pymongo import MongoClient

# Telegram API details
api_id = '12799559'
api_hash = '077254e69d93d08357f25bb5f4504580'
bot_token = '7070968364:AAFCwaipfO9L7B5Aouo-U822ajhaPQDS_ns'

# MongoDB setup
mongo_client = MongoClient('mongodb+srv://test:test@cluster0.q9llhnj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['watermark_bot']
channel_collection = db['channels']

app = Client("watermark_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

@app.on_message(filters.command("connect"))
async def connect_channel(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /connect [channel_id]")
        return

    channel_id = message.command[1]
    channel_collection.update_one(
        {"channel_id": channel_id},
        {"$set": {"watermark": None}},
        upsert=True
    )
    await message.reply_text(f"Connected to channel {channel_id}. Please send the watermark text or image.")

@app.on_message(filters.text & ~filters.command)
async def set_watermark_text(client, message: Message):
    chat_id = str(message.chat.id)
    channel_collection.update_one(
        {"channel_id": chat_id},
        {"$set": {"watermark": message.text}}
    )
    await message.reply_text(f"Watermark set to: {message.text}")

@app.on_message(filters.photo)
async def set_watermark_image(client, message: Message):
    chat_id = str(message.chat.id)
    file = await client.download_media(message.photo.file_id)
    channel_collection.update_one(
        {"channel_id": chat_id},
        {"$set": {"watermark": file}}
    )
    await message.reply_text("Watermark image set.")

@app.on_message(filters.channel & (filters.photo | filters.video))
async def add_watermark(client, message: Message):
    channel_id = str(message.chat.id)
    channel_data = channel_collection.find_one({"channel_id": channel_id})
    watermark = channel_data.get("watermark") if channel_data else None

    if not watermark:
        return

    if message.photo:
        file = await client.download_media(message.photo.file_id)
        watermarked_file = add_watermark_to_image(file, watermark)
        await client.send_photo(channel_id, watermarked_file)
        os.remove(watermarked_file)
    elif message.video:
        file = await client.download_media(message.video.file_id)
        watermarked_file = add_watermark_to_video(file, watermark)
        await client.send_video(channel_id, watermarked_file)
        os.remove(watermarked_file)

def add_watermark_to_image(image_path, watermark):
    base_image = Image.open(image_path).convert("RGBA")
    txt = Image.new("RGBA", base_image.size, (255, 255, 255, 0))

    if isinstance(watermark, str):
        font = ImageFont.load_default()
        draw = ImageDraw.Draw(txt)
        draw.text((10, 10), watermark, fill=(255, 255, 255, 128), font=font)
    else:
        watermark_image = Image.open(watermark).convert("RGBA")
        txt.paste(watermark_image, (10, 10), watermark_image)

    combined = Image.alpha_composite(base_image, txt)
    output_path = f"watermarked_{os.path.basename(image_path)}"
    combined.save(output_path)
    return output_path

def add_watermark_to_video(video_path, watermark):
    video = VideoFileClip(video_path)
    if isinstance(watermark, str):
        txt_clip = TextClip(watermark, fontsize=24, color='white')
        txt_clip = txt_clip.set_position(("right", "bottom")).set_duration(video.duration)
        watermarked = CompositeVideoClip([video, txt_clip])
    else:
        watermark_image = Image.open(watermark)
        watermark_clip = ImageClip(watermark).set_duration(video.duration).resize(height=50).set_position(("right", "bottom"))
        watermarked = CompositeVideoClip([video, watermark_clip])

    output_path = f"watermarked_{os.path.basename(video_path)}"
    watermarked.write_videofile(output_path, codec='libx264')
    return output_path

if __name__ == "__main__":
    app.run()
