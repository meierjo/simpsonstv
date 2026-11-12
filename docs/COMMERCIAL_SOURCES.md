# Commercial source list

These sources provide legitimate archive access or direct download options.
Availability on an archive does not automatically make a commercial public
domain or grant redistribution rights. Review each item's license and uploader
notes, keep a source record, and avoid shipping copyrighted clips on cloned
cards unless permission allows it.

## Best starting points

- Internet Archive - Collection of 90s Commercials:
  <https://archive.org/details/Collectionof90sCommercials>
  - More than one hundred short MPEG-4 files, mostly Nickelodeon-era material.
  - The item offers individual MPEG-4 downloads and an Archive torrent.
  - No clear reuse license is shown; treat it as private archival material.

- Daily TV Calendar - commercials by year:
  <https://dailytvcalendar.com/commercials>
  - Indexes Internet Archive recordings by year and links back to source items.
  - Useful for finding 1989-1999 material without downloading entire decades.

- Internet Archive - Various 1989 Commercials/Promos:
  <https://archive.org/details/1989wrgbbigmoneymoviepromo>
  - Sixty-seven individually downloadable H.264 files from WRGB recordings.
  - The uploader explicitly says they do not own the material; rights are
    unclear, so do not treat archive availability as a reuse license.

## Curated Simpsons-timeslot reels

During 1989-1999 the Twin Cities Fox affiliate carrying first-run Simpsons was
channel 29: KITN, renamed WFTC in 1994. Complete KITN/WFTC Simpsons breaks are
not publicly indexed for every year, so this list uses authentic commercial
breaks recorded during The Simpsons on other Fox affiliates as the national
reference. Source-city local ads should not be labeled as Twin Cities ads.

- 1989 - series premiere, December 17:
  <https://www.youtube.com/watch?v=a1czeKjcRuk>
- 1990 - The Simpsons, March 18:
  <https://www.youtube.com/watch?v=dzIbmplYWOE>
- 1991 - Treehouse of Horror II, October 31:
  <https://www.youtube.com/watch?v=d1xnBCPTUQo>
- 1992 - commercials from The Simpsons, June 25:
  <https://www.dailymotion.com/video/x4zft2f>
- 1993 - Halloween Scare-A-Thon / Treehouse of Horror IV:
  <https://www.youtube.com/watch?v=ItHy8egHcaQ>
- 1994 - Simpsons commercial break, September 18:
  <https://www.youtube.com/watch?v=rrs0nzFkMgA>
- 1995 - Who Shot Mr. Burns? Part Two premiere:
  <https://www.youtube.com/watch?v=TgdX7tnHzFM>
- 1996 - Fox breaks during The Simpsons, November 17:
  <https://www.youtube.com/watch?v=jQXRnNj6lJA>
- 1997 - The Cartridge Family original broadcast:
  <https://www.youtube.com/watch?v=qw22EcIAhK8>
- 1998 - The Trouble with Trillions original broadcast:
  <https://www.youtube.com/watch?v=uwxz5MLR73E>
- 1999 - Take My Wife, Sleaze original broadcast:
  <https://www.dailymotion.com/video/x6l58nk>

### Confirmed Twin Cities station material

- 1992 KITN Minneapolis-Saint Paul commercial reel:
  <https://www.youtube.com/watch?v=MKivHV-Wwq4>
- 1994 KITN Twin Cities commercial breaks:
  <https://www.youtube.com/watch?v=UOJoS_VK0cc>

The same records are stored in `commercials/sources.json` for the planned
automatic download, splitting, provenance, and conversion workflow.

## Year indexes

- 1989: <https://dailytvcalendar.com/1989/commercials>
- 1990: <https://dailytvcalendar.com/1990/commercials>
- 1991: <https://dailytvcalendar.com/1991/commercials>
- 1992: <https://dailytvcalendar.com/1992/commercials>
- 1993: <https://dailytvcalendar.com/1993/commercials>
- 1994: <https://dailytvcalendar.com/1994/commercials>
- 1995: <https://dailytvcalendar.com/1995/commercials>
- 1996: <https://dailytvcalendar.com/1996/commercials>
- 1997: <https://dailytvcalendar.com/1997/commercials>
- 1998: <https://dailytvcalendar.com/1998/commercials>
- 1999: <https://dailytvcalendar.com/1999/commercials>

## Older or rights-researched collections

- Internet Archive - Classic TV Commercials:
  <https://archive.org/details/classic_tv_commercials>
- Duke AdViews at the Internet Archive:
  <https://archive.org/details/adviews>
- Library of Congress guide to television-commercial collections:
  <https://guides.loc.gov/commercials/resources>

These are strongest for pre-1990 material, PSAs, and research. Duke's AdViews
collection is an institutional archive, but access does not by itself grant
commercial redistribution rights.

## Recommended download workflow

1. Open the Internet Archive item page.
2. Read its description, license, and uploader statement.
3. Prefer individual MPEG-4 files over a full item torrent.
4. Record source URL and year next to every selected clip.
5. Convert locally and transfer using SFTP or rsync-over-SSH.
6. Store clips under `commercials/YYYY/` on the Pi.
