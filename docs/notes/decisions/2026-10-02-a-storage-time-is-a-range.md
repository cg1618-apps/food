# A storage time is a range, with a state, in Celsius

- **A range, both ends optional.** The owner's reference sheets state a range
  in almost every row, so a single typical number would have been invented,
  and a "what is about to go off" view computing with it would be computing
  with something nobody said. With both ends optional, "up to 3 days" and "see
  the date" need no sentinel. The cost: the computable number is a choice the
  view makes (the maximum, the minimum or the midpoint), not one the data
  made, so `fridge` on the list summary returns both ends and leaves the
  choice to the caller.
- **A state, in the unique key.** The sheets separate unused from opened, and
  a cooked row is a different thing again, so the key is
  `(ingredient_id, state, method)`.
- Rejected for both: **encoding the range or the state in `notes`**, where
  nothing can compute with or constrain it.
- **Heating stores Celsius only**, and Fahrenheit is computed in the response.
  Two stored temperatures can disagree; one cannot.
