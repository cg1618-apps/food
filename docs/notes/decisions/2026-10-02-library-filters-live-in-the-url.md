# Library filters and the search term live in the URL

A divergence from `media`, whose `useLibraryState` holds them in component
state. A filtered view has to be a link - the ingredient page links to
`/ingredients?category=<id>` - and state cannot be linked to.

A filter click pushes a history entry, so Back undoes it; typing replaces,
debounced, so a search is one entry. media also filters a fully loaded list in
the browser; food sends the filters to the list endpoints, which take them.
