import click
from click.exceptions import ClickException

from elasticsearch.exceptions import NotFoundError

from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry


def register_cli(app):
    @app.cli.group()
    def contentful():
        """Back-end commands."""


    @contentful.command()
    @click.pass_context
    def validate(ctx):
        """
        Validate our configuration
        """
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        space = config.contentful.space()

        codes = [x.code for x in space.locales]
        primary = [x.code for x in space.locales if x.default]
        primary = primary[0] if primary else (codes[0] if codes else 'N/A')

        click.echo("Current config:")
        click.echo(" CONTENTFUL_LANGUAGES=%s" % ','.join(sorted(config.LANGUAGES)))
        click.echo(" CONTENTFUL_DEFAULT_LANGUAGE=%s" % config.DEFAULT_LANGUAGE)
        click.echo("Discovered:")
        click.echo(" CONTENTFUL_LANGUAGES=%s" % ','.join(sorted(codes)))
        click.echo(" CONTENTFUL_DEFAULT_LANG=%s" % primary)

        if not set(config.LANGUAGES) == set(codes):
            click.echo("Please update CONTENTFUL_LANGUAGES to match")
            ctx.exit(1)
        if not config.DEFAULT_LANGUAGE == primary:
            click.echo("Please update CONTENTFUL_DEFAULT_LANGUAGE to match")
            ctx.exit(1)
        click.echo("Configuration matches")
        ctx.exit(0)


    @contentful.command()
    @click.option("--verbose", "-v", count=True)
    @click.option("--dry-run", "-n", default=False, is_flag=True)
    @click.option("--force", "-f", default=False, is_flag=True)
    def update(verbose, dry_run, force):
        """
        Fetches all content types from the back-end, updating where needed
        ---
        Specify --force to force reindexing of all affected content types.
        """
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")

        for ct in config.contentful.content_types():
            if verbose: click.echo(f"Processing content type: '{ct.id}'")
            if not dry_run:
                obj = ContentType(ct.raw)
                if not obj.valid_for_space():
                    if verbose: click.echo("Invalid for space, skipping")
                else:
                    obj.reindex_if_needed(force=force)


    @contentful.command()
    @click.argument("content_type")
    @click.option("--space", default=config.SPACE_ID)
    def remove_type(content_type, space):
        """
        Removes a content type from the search index.
        ---
        Please note that this also removes all content in this content type index.
        """
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        obj = ContentType({"sys": {"id": content_type, "space": {"sys": {"id": space}}}})
        if not obj.valid_for_space():
            raise ClickException("Invalid for space.")
        else:
            obj.unpublish()


    @contentful.command()
    @click.option("--verbose", "-v", count=True)
    @click.option("--token", default=None, required=False)
    def import_all_documents(verbose, token):
        """
        Imports all documents to their specified content type(s).

        ---
        Please note that the storage/removal of documents depends on the CONTENTFUL_ACCESS_TOKEN's access.
        It is _imperative_ that you do not use this method with a PREVIEW token, when ENABLE_UNPUBLISHED is False!
        """
        from contentful import DeletedAsset, DeletedEntry, Asset, Entry as CFEntry
        ASSET_TYPES = (DeletedAsset, Asset)
        ENTRY_TYPES = (CFEntry, DeletedEntry)

        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        if not token:
            if verbose: click.echo("Performing initial sync.")
            sync = config.contentful.sync({'initial': True})
        else:
            if verbose: click.echo("Continuing with existing sync.")
            sync = config.contentful.sync({'sync_token': token})
        while sync.items:
            if verbose: click.echo(f"Sync batch items to process: {len(sync.items)}.")
            processed = 0
            for item in sync.items:
                if isinstance(item, ASSET_TYPES):
                    continue  # We don't index assets
                elif isinstance(item, ENTRY_TYPES):
                    processed += 1
                    obj = Entry(item.raw)
                    if not obj.valid_for_space():
                        continue  # We could echo something but that could get really spammy really quick.
                    if isinstance(item, DeletedEntry):
                        obj.unpublish()
                    else:
                        obj.publish()
            click.echo(f"Processed {processed} items, next token: {sync.next_sync_token}.")
            sync = config.contentful.sync({'sync_token': sync.next_sync_token})


    @contentful.command()
    @click.option("--verbose", "-v", count=True)
    @click.option("--force", "-f", default=False, is_flag=True)
    def full_import(verbose, force):
        """
        Imports the entire space if the database is empty
        ---
        Use the --force toggle to force this regardless of data already existing in the database
        """
        doc = {
            "query": {
                "match_all": {}
            }
        }
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        if not force:
            try:
                results = config.elastic.search(index=config.content_type_index(), body=doc)
                if len(results["hits"]["hits"]) > 0:
                    click.echo(f"Data already exists in database, skipping import. Use --force to force import on an existing database.")
                    return
            except NotFoundError:  # This happens when the index does not exist, at which point we have an empty database.
                click.echo(f"Index {config.content_type_index} does not exist. Assume this is an empty database.")
                pass
        click.echo(f"Importing all content types.")
        update(verbose=verbose)
        click.echo(f"Importing all content. This might take a while...")
        import_all_documents(verbose=verbose)
        

    @contentful.command()
    @click.argument("docid")
    def import_document(docid):
        """
        Import a single document into it's content type.

        ---
        Please note that the storage/removal of documents depends on the CONTENTFUL_ACCESS_TOKEN's access.
        It is _imperative_ that you do not use this method with a PREVIEW token, when ENABLE_UNPUBLISHED is False!
        """
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        try:
            item = config.contentful.entry(docid, {'locale': '*'})
            obj = Entry(item.raw)
            if obj.valid_for_space():
                obj.publish()
            else:
                raise ClickException("Entry is not valid for this space.")
        except:
            raise ClickException("Unable to find item with that content ID.")


    @contentful.command()
    @click.argument("content_type")
    @click.argument("docid")
    def delete_document(content_type, docid):
        """
        Removes a single document from the index.

        ---
        Please note that the storage/removal of documents depends on the CONTENTFUL_ACCESS_TOKEN's access.
        It is _imperative_ that you do not use this method with a PREVIEW token, when ENABLE_UNPUBLISHED is False!
        """
        if not config.contentful:
            raise ClickException("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                                 "CONTENTFUL_ACCESS_TOKEN environment variables.")
        data = {
            'sys': {
                'contentType': {'sys': {'id': content_type}},
                'id': docid,
            },
        }
        obj = Entry(data)
        if obj.valid_for_space():
            obj.delete()
        else:
            click.echo("Entry is not valid for space")
            return
