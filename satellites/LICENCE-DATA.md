# Satellite data licence

- Orbits: CelesTrak's GP element sets for the amateur group, https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur (public data, from the 18th Space Defense Squadron's catalogue). We credit CelesTrak and fetch once a day.
- Transponders and status: SatNOGS DB, https://db.satnogs.org (API: `/api/transmitters/` and `/api/satellites/`).
  - Licence: Creative Commons Attribution-ShareAlike 4.0 International, https://creativecommons.org/licenses/by-sa/4.0/.
  - Listed on our index as: CC BY-SA 4.0 (SatNOGS DB transponders); CelesTrak elements are public data.
- Credit:

  > Satellite orbits from CelesTrak (celestrak.org). Transponder data from SatNOGS DB (db.satnogs.org), CC BY-SA 4.0; the derived satellites file is shared under the same licence.

- Share-alike: `sats.json` is derived from SatNOGS DB data, so it is shared under CC BY-SA 4.0 too. An app that builds on it keeps that licence for the derived data and credits both sources.
- Changes: Ferrite keeps satellites that SatNOGS lists as in orbit with an active transmitter that is FM (voice repeater or transponder, with an uplink) or 1200 baud AFSK (APRS digipeater, with an uplink), every frequency inside 144-148 or 430-440 MHz. It joins them by NORAD number to CelesTrak's elements, writes the two TLE lines from the elements, shortens names to 16 characters and reads a CTCSS tone from the transmitter's description where it names one.
- SatNOGS entries are contributed by volunteers: a transponder may be off, or its tone changed. Check before relying on one.
