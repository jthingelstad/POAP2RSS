import json
import os
import logging
import boto3
import requests
from datetime import datetime, timedelta, timezone
from email.utils import formatdate
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from botocore.exceptions import ClientError
import time
from typing import Dict, List, Optional, Any
import html

try:
    from xml.etree.ElementTree import CDATA  # type: ignore
except ImportError:  # pragma: no cover - Python < 3.9 compatibility
    class CDATA(str):
        """Fallback CDATA representation for older Python versions."""
        pass

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'poap2rss-cache'))

# POAP API configuration
POAP_API_BASE = "https://api.poap.tech"
POAP_API_KEY = os.environ.get('POAP_API_KEY')
POAP_CLIENT_ID = os.environ.get('POAP_CLIENT_ID')
POAP_CLIENT_SECRET = os.environ.get('POAP_CLIENT_SECRET')

# Cache configuration
CACHE_DURATION_MINUTES = 15
MAX_CLAIMS_COUNT = 20
INACTIVITY_THRESHOLD_WEEKS = int(os.environ.get('INACTIVITY_THRESHOLD_WEEKS', '4'))  # Allow override for testing

class POAPAPIClient:
    """POAP API client with authentication and rate limiting"""
    
    def __init__(self):
        self.access_token = None
        self.token_expires_at = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'POAP2RSS/1.0',
            'Accept': 'application/json'
        })
    
    def _get_access_token(self) -> str:
        """Get or refresh access token"""
        if self.access_token and self.token_expires_at and datetime.now(timezone.utc) < self.token_expires_at:
            return self.access_token
        
        logger.info("Refreshing POAP API access token")
        
        auth_url = "https://auth.accounts.poap.xyz/oauth/token"
        auth_data = {
            'audience': 'https://api.poap.tech',
            'grant_type': 'client_credentials',
            'client_id': POAP_CLIENT_ID,
            'client_secret': POAP_CLIENT_SECRET
        }
        
        try:
            response = self.session.post(auth_url, json=auth_data, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            logger.info("Successfully refreshed POAP API access token")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get POAP API access token: {e}")
            raise
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to POAP API"""
        token = self._get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'X-API-Key': POAP_API_KEY
        }
        
        url = f"{POAP_API_BASE}{endpoint}"
        
        try:
            logger.info(f"Making request to: {url} with params: {params}")
            response = self.session.get(url, headers=headers, params=params)
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 403:
                logger.error(f"403 Forbidden - Response body: {response.text}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"POAP API request failed: {url} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise
    
    def get_event_details(self, event_id: int) -> Dict:
        """Get event details by ID"""
        return self._make_request(f"/events/id/{event_id}")
    
    def get_event_poaps(self, event_id: int, limit: int = MAX_CLAIMS_COUNT) -> List[Dict]:
        """Get POAP holders for an event"""
        params = {'limit': limit, 'offset': 0}
        response = self._make_request(f"/event/{event_id}/poaps", params)
        
        # Handle the response structure - POAP API returns data under 'tokens' key
        if isinstance(response, dict) and 'tokens' in response:
            return response['tokens']
        elif isinstance(response, list):
            return response
        else:
            logger.warning(f"Unexpected response structure: {response}")
            return []
    
    def get_address_poaps(self, address: str, limit: int = MAX_CLAIMS_COUNT) -> List[Dict]:
        """Get POAPs for a specific address"""
        params = {'limit': limit, 'offset': 0}
        response = self._make_request(f"/actions/scan/{address}", params)
        return response

class CacheManager:
    """Handle DynamoDB caching operations"""
    
    @staticmethod
    def get_cache_key(feed_type: str, identifier: str) -> str:
        """Generate cache key"""
        return f"{feed_type}:{identifier}"
    
    @staticmethod
    def get_cached_data(cache_key: str) -> Optional[Dict]:
        """Retrieve cached data if still valid"""
        try:
            response = table.get_item(Key={'cache_key': cache_key})
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            cached_time = datetime.fromisoformat(item['cached_at'])
            
            if datetime.now(timezone.utc) - cached_time < timedelta(minutes=CACHE_DURATION_MINUTES):
                logger.info(f"Cache hit for {cache_key}")
                return item['data']
            else:
                logger.info(f"Cache expired for {cache_key}")
                return None
                
        except ClientError as e:
            logger.error(f"Error retrieving cache for {cache_key}: {e}")
            return None
    
    @staticmethod
    def set_cached_data(cache_key: str, data: Dict):
        """Store data in cache"""
        try:
            table.put_item(
                Item={
                    'cache_key': cache_key,
                    'data': data,
                    'cached_at': datetime.now(timezone.utc).isoformat(),
                    'ttl': int(time.time()) + (CACHE_DURATION_MINUTES * 60)
                }
            )
            logger.info(f"Cache updated for {cache_key}")
            
        except ClientError as e:
            logger.error(f"Error caching data for {cache_key}: {e}")

class RSSFeedGenerator:
    """Generate RSS feeds for POAP events and addresses"""
    
    def __init__(self, poap_client: POAPAPIClient):
        self.poap_client = poap_client
    
    def generate_event_feed(self, event_id: int) -> str:
        """Generate RSS feed for a POAP event"""
        logger.info(f"Generating RSS feed for event {event_id}")
        
        try:
            # Get event details and POAPs
            event_details = self.poap_client.get_event_details(event_id)
            logger.info(f"Successfully retrieved event details for {event_id}")
        except Exception as e:
            logger.error(f"Failed to get event details for {event_id}: {e}")
            # Create a fallback event details object
            event_details = {
                'id': event_id,
                'name': f'POAP Event #{event_id}',
                'description': 'Event details unavailable'
            }
        
        try:
            poaps = self.poap_client.get_event_poaps(event_id)
            logger.info(f"Successfully retrieved {len(poaps)} POAPs for event {event_id}")
        except Exception as e:
            logger.error(f"Failed to get POAPs for event {event_id}: {e}")
            # Return empty list if we can't get POAPs
            poaps = []
        
        # Create RSS structure
        rss = Element('rss', version='2.0')
        rss.set('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
        
        channel = SubElement(rss, 'channel')
        
        # Channel metadata
        self._add_channel_metadata(channel, event_details, 'event')
        
        # Add initial event description item
        self._add_event_description_item(channel, event_details)
        
        # Add claim items
        if poaps:
            for poap in poaps:
                self._add_claim_item(channel, poap, event_details)
        
        # Check for inactivity and add alert if needed
        self._check_and_add_inactivity_alert(channel, event_details, poaps)
        
        return self._format_xml(rss)
    
    def generate_address_feed(self, address: str) -> str:
        """Generate RSS feed for an address's POAP collection"""
        logger.info(f"Generating RSS feed for address {address}")
        
        # Get POAPs for address
        poaps = self.poap_client.get_address_poaps(address)
        
        # Create RSS structure
        rss = Element('rss', version='2.0')
        rss.set('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
        
        channel = SubElement(rss, 'channel')
        
        # Channel metadata for address feed
        self._add_address_channel_metadata(channel, address)
        
        # Add POAP collection items
        if poaps:
            for poap in poaps[:MAX_CLAIMS_COUNT]:
                self._add_address_poap_item(channel, poap, address)
        
        return self._format_xml(rss)
    
    def _add_channel_metadata(self, channel: Element, event_details: Dict, feed_type: str):
        """Add RSS channel metadata"""
        event_name = event_details.get('name', 'Unknown Event')
        event_id = event_details.get('id', 'unknown')
        
        SubElement(channel, 'title').text = f"POAP: {event_name}"
        SubElement(channel, 'description').text = f"Activity for {event_name} POAP drop."
        SubElement(channel, 'link').text = f"https://poap.gallery/drops/{event_id}"
        SubElement(channel, 'language').text = 'en-us'
        SubElement(channel, 'lastBuildDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        SubElement(channel, 'generator').text = 'POAP2RSS/1.0'
        
        # Add atom:link for self-reference
        atom_link = SubElement(channel, 'atom:link')
        atom_link.set('href', f"https://app.poap2rss.com/event/{event_id}")
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')
            
    def _add_address_channel_metadata(self, channel: Element, address: str):
        """Add RSS channel metadata for address feeds"""
        # Try to get ENS name for the address
        ens_name = self._get_ens_name(address)
        display_name = ens_name if ens_name else f"{address[:6]}...{address[-4:]}"
        
        SubElement(channel, 'title').text = f"POAP: {display_name} Collection"
        SubElement(channel, 'description').text = f"Latest POAP tokens for {display_name}."
        SubElement(channel, 'link').text = f"https://collectors.poap.xyz/scan/{address}"
        SubElement(channel, 'language').text = 'en-us'
        SubElement(channel, 'lastBuildDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        SubElement(channel, 'generator').text = 'POAP2RSS/1.0'
    
        # Add atom:link for self-reference
        atom_link = SubElement(channel, 'atom:link')
        atom_link.set('href', f"https://app.poap2rss.com/address/{address}")
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')

    def _add_event_description_item(self, channel: Element, event_details: Dict):
        """Add initial event description item"""
        item = SubElement(channel, 'item')
        
        event_name = event_details.get('name', 'Unknown Event')
        event_description = event_details.get('description', 'No description available')
        
        SubElement(item, 'title').text = f"{event_name} Event Details"
        
        # Create description with event details
        description_html = f"""
        <h3>{event_name}</h3>
        <p>{event_description}</p>
        """
        
        if event_details.get('image_url'):
            description_html += f'<img src="{event_details["image_url"]}" width="500" height="500" />'
        
        if event_details.get('city'):
            description_html += f"<p><strong>Location:</strong> {event_details['city']}"
            if event_details.get('country'):
                description_html += f", {event_details['country']}"
            description_html += "</p>"
                
        description_elem = SubElement(item, 'description')
        description_elem.text = CDATA(description_html)
        SubElement(item, 'guid').text = f"https://poap.gallery/drops/{event_details.get('id', 'unknown')}"
        SubElement(item, 'link').text = f"https://poap.gallery/drops/{event_details.get('id', 'unknown')}"
        
        # Use event date for timestamp - try multiple possible date fields
        event_timestamp = None
        
        # Try different date fields that might be in the event details
        for date_field in ['start_date', 'end_date', 'event_date', 'created_date', 'expiry_date']:
            if event_details.get(date_field):
                try:
                    date_str = event_details[date_field]
                    # Handle different date formats
                    if date_str.endswith('Z'):
                        event_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    elif '+' in date_str:
                        event_datetime = datetime.fromisoformat(date_str)
                    else:
                        # Assume UTC if no timezone info
                        event_datetime = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                    
                    event_timestamp = event_datetime.timestamp()
                    logger.info(f"Using {date_field} for event timestamp: {date_str}")
                    break
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse {date_field} '{date_str}': {e}")
                    continue
        
        # If no valid event date found, use current time as fallback
        if event_timestamp is None:
            logger.warning("No valid event date found, using current time")
            event_timestamp = time.time()
        
        SubElement(item, 'pubDate').text = formatdate(timeval=event_timestamp, localtime=False, usegmt=True)
    
    def _add_claim_item(self, channel: Element, poap: Dict, event_details: Dict):
        """Add RSS item for a POAP claim"""
        item = SubElement(channel, 'item')
        
        # Get claimant info - note the POAP API returns 'id' for token ID
        owner_address = poap.get('owner', {}).get('id', 'unknown')
        ens_name = poap.get('owner', {}).get('ens', '')
        display_name = ens_name if ens_name else f"{owner_address[:6]}...{owner_address[-4:]}"
        token_id = poap.get('id', 'unknown')  # This is the token ID in the API response

        # Item content
        SubElement(item, 'title').text = f""
        SubElement(item, 'author').text = f"{display_name}"
        
        description = f"""
        <p><strong><a href="https://collectors.poap.xyz/scan/{owner_address}">{display_name}</a></strong>
        claimed POAP <a href="https://collectors.poap.xyz/token/{token_id}">{token_id}</a> for 
        <strong><a href="https://poap.gallery/drops/{event_details.get('id', 'Unknown Event')}">{event_details.get('name', 'Unknown Event')}</a></strong></p>
        <p><img src="{event_details["image_url"]}" width="500" height="500" /></p>
        """
        
        description_elem = SubElement(item, 'description')
        description_elem.text = CDATA(description)
        SubElement(item, 'guid').text = f"https://collectors.poap.xyz/token/{token_id}"
        SubElement(item, 'link').text = f"https://collectors.poap.xyz/token/{token_id}"
        
        # Use creation date for timestamp with proper timezone handling
        if poap.get('created'):
            try:
                # Parse the datetime string and ensure it's timezone-aware
                created_str = poap['created']
                if created_str.endswith('Z'):
                    created_datetime = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                elif '+' in created_str or created_str.endswith('UTC'):
                    created_datetime = datetime.fromisoformat(created_str.replace('UTC', ''))
                    if created_datetime.tzinfo is None:
                        created_datetime = created_datetime.replace(tzinfo=timezone.utc)
                else:
                    # Assume UTC if no timezone info - this handles '2025-07-03 03:55:35' format
                    created_datetime = datetime.fromisoformat(created_str).replace(tzinfo=timezone.utc)
                
                SubElement(item, 'pubDate').text = formatdate(timeval=created_datetime.timestamp(), localtime=False, usegmt=True)
            except ValueError as e:
                logger.warning(f"Could not parse created date '{created_str}': {e}")
                SubElement(item, 'pubDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        else:
            SubElement(item, 'pubDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
    
    def _add_address_poap_item(self, channel: Element, poap: Dict, address: str):
        """Add RSS item for a POAP in an address feed"""
        item = SubElement(channel, 'item')
        
        event_name = poap.get('event', {}).get('name', 'Unknown Event')
        event_id = poap.get('event', {}).get('id', 'unknown')
        event_image_url = poap.get('event', {}).get('image_url', 'unknown')
        
        SubElement(item, 'title').text = f""
        SubElement(item, 'author').text = address
        
        description = f"""
        <p>Collected POAP <a href="https://collectors.poap.xyz/token/{poap.get('tokenId', 'unknown')}">{poap.get('tokenId', 'unknown')}</a> for <strong><a href="https://poap.gallery/drops/{event_id}">{event_name}</a></strong>.</p>
        <p><img src="{event_image_url}" width="500" height="500" /></p>
        """
        
        description_elem = SubElement(item, 'description')
        description_elem.text = CDATA(description)
        SubElement(item, 'guid').text = f"https://collectors.poap.xyz/token/{poap.get('tokenId', '')}"
        SubElement(item, 'link').text = f"https://collectors.poap.xyz/token/{poap.get('tokenId', '')}"
        
        if poap.get('created'):
            try:
                created_datetime = datetime.fromisoformat(poap['created'].replace('Z', '+00:00'))
                SubElement(item, 'pubDate').text = formatdate(timeval=created_datetime.timestamp(), localtime=False, usegmt=True)
            except ValueError:
                SubElement(item, 'pubDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
    
    def _check_and_add_inactivity_alert(self, channel: Element, event_details: Dict, poaps: List[Dict]):
        """Check for inactivity and add alert if needed"""
        if not poaps:
            logger.info("No POAPs found, skipping inactivity check")
            return
        
        # Get the most recent claim date
        most_recent_claim = None
        for poap in poaps:
            if poap.get('created'):
                try:
                    # Parse the datetime string and ensure it's timezone-aware
                    created_str = poap['created']
                    if created_str.endswith('Z'):
                        claim_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    elif '+' in created_str or created_str.endswith('UTC'):
                        claim_date = datetime.fromisoformat(created_str.replace('UTC', ''))
                        if claim_date.tzinfo is None:
                            claim_date = claim_date.replace(tzinfo=timezone.utc)
                    else:
                        # Assume UTC if no timezone info
                        claim_date = datetime.fromisoformat(created_str).replace(tzinfo=timezone.utc)
                    
                    if most_recent_claim is None or claim_date > most_recent_claim:
                        most_recent_claim = claim_date
                except ValueError as e:
                    logger.warning(f"Could not parse date '{created_str}': {e}")
                    continue
        
        if most_recent_claim is None:
            logger.warning("No valid claim dates found, skipping inactivity check")
            return
        
        # Calculate weeks since last claim
        now = datetime.now(timezone.utc)
        time_diff = now - most_recent_claim
        weeks_since_last_claim = time_diff.days // 7
        
        logger.info(f"Most recent claim: {most_recent_claim}")
        logger.info(f"Current time: {now}")
        logger.info(f"Days since last claim: {time_diff.days}")
        logger.info(f"Weeks since last claim: {weeks_since_last_claim}")
        logger.info(f"Inactivity threshold: {INACTIVITY_THRESHOLD_WEEKS} weeks")
        
        # Check if it's been more than the threshold weeks since last claim
        if weeks_since_last_claim >= INACTIVITY_THRESHOLD_WEEKS:
            logger.info(f"Adding inactivity alert for {weeks_since_last_claim} weeks")
            item = SubElement(channel, 'item')
            
            if weeks_since_last_claim == INACTIVITY_THRESHOLD_WEEKS:
                title = f"No POAP claims in the last {weeks_since_last_claim} weeks."
            else:
                title = f"{weeks_since_last_claim} weeks with no claims"
            
            SubElement(item, 'title').text = title
            SubElement(item, 'description').text = f"""
            <p>There have been no new POAP claims for this event in {weeks_since_last_claim} weeks.</p>
            <p>The event may be over. Consider unsubscribing from this feed if no further activity is expected.</p>
            <p><em>Last claim was on {most_recent_claim.strftime('%Y-%m-%d %H:%M:%S UTC')}</em></p>
            """
            
            # Use unique GUID for each week to ensure new notifications
            SubElement(item, 'guid').text = f"https://www.poap2rss.com/inactive.html?event={event_details.get('id', 'unknown')}&week={weeks_since_last_claim}"
            SubElement(item, 'link').text = f"https://www.poap2rss.com/inactive.html?event={event_details.get('id', 'unknown')}&week={weeks_since_last_claim}"
            SubElement(item, 'pubDate').text = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        else:
            logger.info(f"No inactivity alert needed (only {weeks_since_last_claim} weeks since last claim)")
    
    
    def _get_ens_name(self, address: str) -> Optional[str]:
        """Get ENS name for an address (simplified - would need proper ENS resolution)"""
        # In a real implementation, you'd call an ENS resolver
        # For now, return None as ENS resolution requires additional setup
        return None
    
    def _format_xml(self, root: Element) -> str:
        """Format XML with proper indentation"""
        rough_string = tostring(root, encoding='unicode')
        parsed = minidom.parseString(rough_string)

        # Convert <description> contents back to CDATA sections
        for desc in parsed.getElementsByTagName('description'):
            if desc.childNodes:
                text = ''.join(node.data for node in desc.childNodes)
                text = html.unescape(text)
                for child in list(desc.childNodes):
                    desc.removeChild(child)
                desc.appendChild(parsed.createCDATASection(text))

        return parsed.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')

def lambda_handler(event, context):
    """Lambda function handler"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Parse request
        path = event.get('path', '')
        path_parts = path.strip('/').split('/')
        
        if len(path_parts) < 2:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid path. Use /event/{id} or /address/{address}'})
            }
        
        feed_type = path_parts[0]  # 'event' or 'address'
        identifier = path_parts[1]  # event_id or address
        
        if feed_type not in ['event', 'address']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Feed type must be "event" or "address"'})
            }
        
        # Check cache first
        cache_key = CacheManager.get_cache_key(feed_type, identifier)
        cached_data = CacheManager.get_cached_data(cache_key)
        
        if cached_data:
            logger.info(f"Returning cached RSS feed for {cache_key}")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/rss+xml; charset=utf-8',
                    'Cache-Control': f'max-age={CACHE_DURATION_MINUTES * 60}'
                },
                'body': cached_data['rss_xml']
            }
        
        # Generate fresh feed
        poap_client = POAPAPIClient()
        feed_generator = RSSFeedGenerator(poap_client)
        
        if feed_type == 'event':
            try:
                event_id = int(identifier)
                rss_xml = feed_generator.generate_event_feed(event_id)
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Event ID must be a number'})
                }
        else:  # address
            rss_xml = feed_generator.generate_address_feed(identifier)
        
        # Cache the result
        cache_data = {'rss_xml': rss_xml}
        CacheManager.set_cached_data(cache_key, cache_data)
        
        logger.info(f"Generated and cached RSS feed for {cache_key}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/rss+xml; charset=utf-8',
                'Cache-Control': f'max-age={CACHE_DURATION_MINUTES * 60}'
            },
            'body': rss_xml
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

# For testing locally
if __name__ == "__main__":
    # Test event
    test_event = {
        'path': '/event/12345',
        'httpMethod': 'GET'
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

