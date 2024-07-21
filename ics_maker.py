import streamlit as st
import anthropic
from PIL import Image
from io import BytesIO
from ics import Calendar, Event
import base64
from datetime import datetime, timedelta
import pytz
import json
from dateutil import parser
import logging
from typing import Optional, Dict, Any

# Constants
CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
MAX_TOKENS = 1000
TEMPERATURE = 0
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant that extracts event details from text and creates ICS files."
IST_TIMEZONE = 'Asia/Kolkata'

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Anthropic API key from secrets
client = anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])

def extract_text_from_image(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system="You are a helpful assistant that extracts text from images.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_str
                            }
                        },
                        {
                            "type": "text",
                            "text": "Please extract all the text from this image."
                        }
                    ]
                }
            ]
        )
        return message.content
    except Exception as e:
        logger.error(f"An error occurred while extracting text from image: {str(e)}")
        st.error(f"An error occurred while extracting text from image: {str(e)}")
        return ""

def claude_request(prompt: str, system: str = DEFAULT_SYSTEM_PROMPT) -> Optional[str]:
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        return message.content
    except Exception as e:
        logger.error(f"An error occurred while calling Claude: {str(e)}")
        st.error(f"An error occurred while calling Claude: {str(e)}")
        return None

def parse_event_details(response: str) -> Dict[str, Any]:
    if isinstance(response, list) and len(response) > 0:
        response = response[0].text
    return json.loads(response)

def create_ics_event(event_details: Dict[str, Any]) -> Calendar:
    c = Calendar()
    e = Event()
    e.name = event_details['name']
    
    ist = pytz.timezone(IST_TIMEZONE)
    start_time = parser.parse(event_details['start_time'])
    if start_time.tzinfo is None:
        start_time = ist.localize(start_time)
    
    if event_details['end_time']:
        end_time = parser.parse(event_details['end_time'])
        if end_time.tzinfo is None:
            end_time = ist.localize(end_time)
    else:
        end_time = start_time + timedelta(hours=1)
    
    e.begin = start_time
    e.end = end_time
    e.description = event_details.get('description', '')
    e.location = event_details.get('location', '')
    c.events.add(e)
    
    return c

def generate_ics_from_text(text: str) -> Optional[Calendar]:
    user_prompt = f"""Extract event details from the following text and format them as a JSON object with keys 'name', 'start_time', 'end_time', 'description', and 'location'. If no time zone is specified, assume Indian Standard Time (IST). If end_time is not specified, leave it as null. Ensure the JSON is valid and properly formatted. Respond only with the JSON object, no other text. Text: {text}"""
    
    response = claude_request(user_prompt)
    
    if response:
        try:
            event_details = parse_event_details(response)
            return create_ics_event(event_details)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event details: {str(e)}")
            st.error(f"Failed to parse event details: {str(e)}")
            st.text("Claude's response:")
            st.text(response)
        except KeyError as e:
            logger.error(f"Missing required field in event details: {str(e)}")
            st.error(f"Missing required field in event details: {str(e)}")
            st.text("Parsed event details:")
            st.text(event_details)
        except ValueError as e:
            logger.error(f"Invalid date-time format: {str(e)}")
            st.error(f"Invalid date-time format: {str(e)}")
            st.text("Date-time values:")
            st.text(f"Start time: {event_details.get('start_time')}")
            st.text(f"End time: {event_details.get('end_time')}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")
            st.error(f"An unexpected error occurred: {str(e)}")
            st.text("Claude's response:")
            st.text(response)
    else:
        logger.error("Failed to get a valid response from Claude")
        st.error("Failed to get a valid response from Claude")
    
    return None

st.title("Event to ICS Converter")

input_type = st.radio("Select input type:", ("Text", "Image"))

if input_type == "Text":
    user_input = st.text_area("Enter event details:")
else:
    uploaded_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        user_input = extract_text_from_image(image)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        st.write("Extracted text:")
        st.write(user_input)

if st.button("Submit"):
    if user_input:
        with st.spinner("Processing..."):
            ics_calendar = generate_ics_from_text(user_input)
            if ics_calendar:
                ics_content = str(ics_calendar)
                
                st.success("ICS file generated successfully!")
                st.download_button(
                    label="Download ICS File",
                    data=ics_content,
                    file_name="event.ics",
                    mime="text/calendar"
                )
            else:
                st.error("Failed to generate ICS file. Please check the error messages above and try again.")
    else:
        st.warning("Please provide input before submitting.")

# Debug information
st.subheader("Debug Information")
if st.checkbox("Show debug info"):
    st.write("User Input:", user_input)
