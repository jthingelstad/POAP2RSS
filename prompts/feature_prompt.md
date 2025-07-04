PROMPT for Deep Research:

> Please help me explore and expand the features for POAP2RSS service that provides an RSS feed to subscribe to claims from a POAP event. The POAP events do not have an RSS feed, so I want to create a service that provides an RSS feed for a user using the POAP API to populate the data. 
> 
> I’m already considering:
> 
> - Only include entries for most recent 20 claims
> - If no claims in 4 weeks, add an entry that states that and suggests the user remove the feed. Change this for every additional week and change the RSS feed ID so it will show up as new to the user.
> - Provide ENS names in the RSS item and set the Author of the item to the ENS name or address that claimed the token. Set the date and time of the item to the collected time.
> - Add an initial item to all feeds that shows the description of the POAP Event and uses the timestamp for the event.
> - Use DynamoDB to cache results from POAP API for 15 minutes

Clarification question:

> Could you share more about the user audience and the intended use cases for the POAP2RSS service? For example, is it for collectors to track participation, for event organizers to monitor engagement, or for public observers? Also, are you targeting a particular feed reader or platform? This will help tailor feature ideas to your goals.

It is for any user including all three of those, however I suspect it will be most frequently used by the creator of the POAP event to monitor claims. I also expect it will be used in Automation -- for example to send a message anytime a claim is made by connecting the RSS feed to something like Zapier. The RSS feed should be fully standard so it can be used in any way desired.

