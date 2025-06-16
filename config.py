import os

# --------------------------- basic credentials --------------------------- #
# If the environment variable is *unset* or *empty*, fall back to the value
# that is written in code.
BOT_TOKEN = (os.getenv("BOT_TOKEN") or
             "7747457753:AAHhougqltSLykcnMiRix14ZQwEk3etkw3Y")

# multiple admin IDs separated by commas
_admin_raw = os.getenv("ADMIN_IDS") or "6954322783"
ADMIN_IDS = [int(x) for x in _admin_raw.split(",") if x.strip()]

RECIPIENT_ID = int(os.getenv("RECIPIENT_ID") or "7433229383")
TRANSFER_FEE = int(os.getenv("TRANSFER_FEE") or "25")

# --------------------------- optional GPT prompt ------------------------- #
GPT_PROMPT = (os.getenv("GPT_PROMPT") or
              "You are a business assistant. Respond briefly and professionally when the owner is offline.")
