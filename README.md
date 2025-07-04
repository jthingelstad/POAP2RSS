# POAP2RSS

**POAP2RSS** is a service that generates an RSS feed for any [POAP](https://poap.xyz) event, making it easy to subscribe to claim activity in real time. Whether you're an event organizer, a collector, or using automation tools like Zapier, POAP2RSS gives you a clean, standards-compliant feed of the latest claims.

🔗 Visit [poap2rss.com](https://poap2rss.com) for full documentation, usage details, and examples.

## ✨ Features

- 🔄 **Live Feed of Claims:** Track the 20 most recent claims from any POAP event.
- 👤 **ENS Support:** Displays ENS names as the author of each RSS item (with fallback to wallet address).
- 📅 **Timestamped Entries:** Each claim uses the actual collection time as the publish date.
- ⏰ **Inactivity Alerts:** If no claims occur for 4+ weeks, the feed posts a gentle reminder (updated weekly).
- 🖼 **Event Metadata:** Includes an initial item with the POAP event’s description and image.
- ⚡ **Smart Caching:** Uses a 15-minute cache to minimize API calls and improve responsiveness.
- 🤖 **Fully Standard RSS:** Works out of the box with feed readers and automation platforms like IFTTT, Zapier, and Slack.

## 🧩 Use Cases

- Event creators monitoring real-time participation.
- Fans following collector activity (coming soon).
- Automations triggered on claim (e.g. post to Discord, tweet, log to Notion).
- RSS-based archiving of attendance patterns.

## 🔐 Design Goals

- Minimal latency with caching for scalability.
- Zero tracking or user data collection.
- Built on open protocols for maximum portability and reuse.

## 🛣 Roadmap

- [ ] Address-based collection feeds (e.g. `rss/address/jamie.eth`)
- [ ] Batch feeds for multiple events
- [ ] JSON Feed output support
- [ ] Web-based feed creation UI

## 🤝 Contributing

Issues and pull requests welcome! Check open issues or submit ideas. For feedback, contact via [poap2rss.com](https://poap2rss.com).

## 📄 License

MIT License. See [LICENSE](./LICENSE) for details.

---

> Brought to life to make POAPs more open, programmable, and connected to the wider web.


Made my Jamie Thingelstad, OpenAI 4-o, Anthropic Sonnet 4
