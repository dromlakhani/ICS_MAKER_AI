import streamlit as st
import anthropic
from PIL import Image
import pytesseract
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import json
from dateutil import parser

# Set up Anthropic API key from secrets
client = anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])

def extract_text_from_image(image):
    return pytesseract.image_to_string(image)

def claude_request(prompt, system="You are a helpful assistant."):
    try:
        message = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
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
        st.error(f"An error occurred while calling Claude: {str(e)}")
        return None

def generate_ics_from_text(text):
    # Use Claude to extract event details
    system_prompt = "You are a helpful assistant that extracts event details from text and creates ICS files."
    user_prompt = f"""Extract event details from the following text and format them as a JSON object with keys 'name', 'start_time', 'end_time', 'description', and 'location'. If no time zone is specified, assume Indian Standard Time (IST). If end_time is not specified, leave it as null. Ensure the JSON is valid and properly formatted. Respond only with the JSON object, no other text. Text: {text}"""
    
    response = claude_request(user_prompt, system_prompt)
    
    if response:
        try:
            # Check if response is a list and get the first item
            if isinstance(response, list) and len(response) > 0:
                response = response[0].text
            
            # Parse the JSON string
            event_details = json.loads(response)
            
            # Create ICS file
            c = Calendar()
            e = Event()
            e.name = event_details['name']
            
            # Parse start time, assuming IST if no timezone is specified
            ist = pytz.timezone('Asia/Kolkata')
            start_time = parser.parse(event_details['start_time'])
            if start_time.tzinfo is None:
                start_time = ist.localize(start_time)
            
            # Handle end time
            if event_details['end_time']:
                end_time = parser.parse(event_details['end_time'])
                if end_time.tzinfo is None:
                    end_time = ist.localize(end_time)
            else:
                # If end time is not specified, set it to 1 hour after start time
                end_time = start_time + timedelta(hours=1)
            
            e.begin = start_time
            e.end = end_time
            e.description = event_details.get('description', '')
            e.location = event_details.get('location', '')
            c.events.add(e)
            
            return c
        except json.JSONDecodeError as e:
            st.error(f"Failed to parse event details: {str(e)}")
            st.text("Claude's response:")
            st.text(response)
        except KeyError as e:
            st.error(f"Missing required field in event details: {str(e)}")
            st.text("Parsed event details:")
            st.text(event_details)
        except ValueError as e:
            st.error(f"Invalid date-time format: {str(e)}")
            st.text("Date-time values:")
            st.text(f"Start time: {event_details.get('start_time')}")
            st.text(f"End time: {event_details.get('end_time')}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            st.text("Claude's response:")
            st.text(response)
    else:
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