# How does the laptop serve the basecamp address?

Type: grilling
Status: open

## Question

The app's address is `https://basecamp.<tailnet>.ts.net`. A Tailscale Service can only be hosted by a device with a tag-based identity, not one signed in as a user, and your laptop is a user device. Which way of producing that address should v1 use?

- **Tag the laptop** and make it the host of a `basecamp` Service. Your laptop's tailnet identity becomes the tag's, and its access is then governed by tag rules instead of your user.
- **Run a separate tagged Tailscale node just for the app** on the laptop (for example a Tailscale container next to the app) that hosts the Service. The same container moves to the VPS later. This needs Docker or similar.
- **No Service:** a dedicated node named `basecamp` (a container, or the open-source `tailscaled` in userspace mode) runs `tailscale serve`. Moving to a VPS means retiring the laptop's node and naming the VPS node `basecamp`. There's no Service approval and nothing in beta, but a brief gap while the name moves.

Whichever is chosen, nothing may claim the name `basecamp` in the tailnet in the meantime.
