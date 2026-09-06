# Body view

Body is an experimental view of recorded training and body measurements. Choose
it from the Health panel. Overview opens first on a new browser; an explicit
view choice is remembered for that Home Assistant user in that browser.

The figure has fixed proportions. Weight, body fat and lean mass don't change
its shape. Flip it to see the back, or use the named region controls with a
keyboard. Opening a region shows the recorded workouts behind it. Body
measurements use the same values, trends, source claims and exclusion controls
as Overview.

## What the colors mean

Each usable, non-warmup set contributes one recorded set to the muscle regions
listed for its exercise. Its contribution fades linearly from one when the
workout ends to zero seven days later. The region with the largest remaining
contribution gets the strongest shade; other regions are shaded in proportion.
The detail view also shows the plain set count before fading.

This is a view of recorded sets. It doesn't estimate recovery or compare the
physical load of different exercises. A set mapped to several regions appears
in each of them, so regional counts shouldn't be added together as a workout
total. Weight and reps remain available in workout detail.

A usable set includes positive reps, duration or distance. Numbers must be
finite and nonnegative; reps must be whole numbers. Warmup, warm-up and warm up
set types are excluded from the color calculation. Workouts without usable
sets still appear, with a count explaining why they don't light up the figure.

Sleep and heart placeholders say "Not available yet." They are reserved for
future features.

## Exercise names and map gaps

The map lives in
[`exercise_map.json`](../custom_components/health_assistant/exercise_map.json).
It works with exercise detail from any source that supplies the supported
shape. Matching normalizes Unicode, letter case and whitespace, then requires
an exact alias. It doesn't guess from part of a name. Unrecognized exercises
appear in the unmapped list; their sets don't produce muscle color.

The map is intentionally small. Each entry includes its exercise reference,
aliases and a broad list of regions. It groups related muscles for this figure
and does not claim to represent every muscle involved in a movement. When
adding an alias, check its exercise and equipment, confirm the regions against
the linked reference, and run the map and figure tests.

## Data limits

Body considers completed workouts ending within the last seven days. It shows
at most 100 workouts and says when more exist. Each workout can contribute up
to 100 exercises, 100 sets per exercise and 1,000 sets in total. A saved detail
payload over 256 KiB is left out of this view. Limited or invalid detail is
marked incomplete; the stored workout is kept.

The unmapped list shows up to 20 names along with the total number of unmapped
exercise entries. Names and notes have display limits. Workout detail returns
only source identity, times and supported exercise fields. Other saved
provenance is kept out of the panel.

Hevy capture currently starts with the latest completed workout exposed by
the installed Hevy Tracker integration. It doesn't import a full workout
history. Empty regions can mean missing detail or a map gap as well as no
recent recorded sets.
