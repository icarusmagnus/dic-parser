# Connecteur AMfine (licence) — drop-in pour couvrir TOUS les assureurs

**amfinesoft (AMfine) est le fournisseur dominant** : il sert 50+ assureurs et
héberge à la fois les DIC de **contrats** et de **fonds**. Une licence commerciale
AMfine donne accès au **catalogue complet** de tous ses assureurs clients.

## Comment brancher une licence

1. Obtenir d'AMfine l'export du catalogue (assureurs + produits + IDs), OU l'accès
   à leur API de liste.
2. Déposer un ou plusieurs fichiers **CSV** dans ce dossier (`data/amfine_inbox/`),
   colonnes :

   | colonne | obligatoire | exemple |
   |---|---|---|
   | `client` | oui | `CARDIF`, `SOGECAP`, `AXA`, `GENERALI`… (code assureur amfinesoft) |
   | `type`   | non (défaut `product`) | `product` (contrat) ou `underlying` (fonds) |
   | `id`     | oui | ID produit (ou ISIN pour un fonds) |
   | `name`   | non | libellé (sinon récupéré du PDF) |
   | `key`    | non | clé d'accès (sinon variable d'env `AMFINE_KEY`, sinon aucune) |

3. Au prochain run (quotidien, automatique), le pipeline **télécharge et parse
   tout le catalogue** — tous les assureurs d'un coup, sans code à écrire.

Voir `catalogue.csv.example` pour le format exact.

## Sans licence

Ce dossier reste vide → le connecteur ne fait rien. Les 7 assureurs déjà cracqués
publiquement (Cardif, Generali, CNP, Allianz, Sogecap, AXA, Suravenir) continuent
de se mettre à jour normalement.
