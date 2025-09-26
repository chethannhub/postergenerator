from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

import os
from dotenv import load_dotenv

load_dotenv()

BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

#commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! I am your poster generation bot. What can I create for you today?')
    
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('You can use the following commands:\n/start - Start the bot\n/help - Show this help message\nJust send me a message with your poster idea!')
    
    
# Responses

def handle_response(text: str) -> str:
    
    
    if 'hello' in text.lower():
        return 'Hello! How can I assist you with your poster today?'
    
    if 'how are you' in text.lower():
         return 'I\'m just a bot, but I\'m here to help you create amazing posters! What would you like to design today?'
    
    if 'poster' in text.lower():
         return 'Great! I can help you create a poster. Please provide more details about the theme, colors, and style you have in mind.'
    
    if 'thank you' in text.lower() or 'thanks' in text.lower():
         return 'You\'re welcome! If you have any more poster ideas or need further assistance, feel free to ask.'
    
    return "I didn't understand that. Can you please rephrase?"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_type:str = update.message.chat.type
    text:str = str(update.message.text)
    
    print(f'User ({update.message.chat.id}) in {message_type} sent: {text}')
    
    if message_type == 'group':
        if BOT_USERNAME in text:
            new_text = text.replace(BOT_USERNAME, '').strip()
            response = handle_response(new_text)
        else:
            return 
        
    else:
        response = handle_response(text)
        
    print("Bot:", response)
    await update.message.reply_text(response)
    
    
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f'Update {update} caused error {context.error}')
    
if __name__ == '__main__':
    print("Starting bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Errors
    app.add_error_handler(error)

    # Poll the bot
    print("Polling...")
    app.run_polling(poll_interval=3)