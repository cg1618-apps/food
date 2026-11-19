# A refused recipe save writes nothing

The recipe service validates every id, the own-dish rule and the cycle guard
before its first write - new dishes, stubs and authors included - and touches
the recipe row only after them. Relying on the request's rollback alone would
hold in production and not in a session that is never rolled back, which is
where a half-written row would be noticed last.
