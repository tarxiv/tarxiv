# Object Page & Schema Updates

We're changing schema! There's a bit of a difference in how this is going to, you can see the differences in 
new_sample.json and old_sample.json, which will essentially just change how we grab metadata for a given object. 

The things I'd like implemented are:
- [x] Update the object page to use the new schema
- [x] Fix the aladin plot so it is positioned higher in the object page, alongside the lightcurve. Ideally this should 
be a 3:1 split, with the lightcurve taking up 3/4 of the horizontal space and the aladin plot taking up 1/4.
- [x] The object page should also hook into the new /citations endpoint to display the bibtex citation text for the 
object. This should be displayed in a box that is easily copyable, and should be placed below the lightcurve and aladin 
plot, ideally with a copy button next to it for easy copying.
- [x] The Full Metadata section should be collapsible, and should be collapsed by default. 
- [x] The plot on the cone search page should be fixed, namely by being replaced with the aladin widget and the results 
of the cone search overlaid. Hovering over a found result object should highligh the relevant tick/marker on the aladin 
plot.