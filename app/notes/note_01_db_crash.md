---
title: Database crashed out today.
date: 2025-09-17
tags: naarmlist, tech, website, programming, nosql
---

Today I noticed the database was down. Luckily I had taken a backup recently when looking to deploy some new features. Sadly however looking at my backup function...

```python
def export_database():
    db = get_db_connection()
    export_data = {
        'events': list(db.events.find()),
        'venues': list(db.venues.find()),
     } 
```

...there was no `'artists': list(db.Artists.find())` so we lost all the entries since March.

While fixing that I thought I may as well get around to adding "venues" properly (it has been around for ages but as a "hidden page", just an auto-generated list with no edit/link function) as well as a directory for organisers/promoters.

As this list grows it will start auto-populating the main page and generating hot links like with the [Artist Directory](https://naarmlist.net/artists).
