from .store import LookupConfig, set_lookup_config


def add_lookup_config_args(parser):
    """Add the per-source delay and User-Agent options to an argparse parser."""
    parser.add_argument(
        "--delay-dblp",
        metavar="SECONDS",
        type=float,
        default=0,
        help="Delay in seconds before DBLP lookups (default: 0)",
    )
    parser.add_argument(
        "--delay-arxiv",
        metavar="SECONDS",
        type=float,
        default=0,
        help="Delay in seconds before arXiv lookups (default: 0)",
    )
    parser.add_argument(
        "--delay-eprint",
        metavar="SECONDS",
        type=float,
        default=0,
        help="Delay in seconds before ePrint lookups (default: 0)",
    )
    parser.add_argument(
        "--delay-doi",
        metavar="SECONDS",
        type=float,
        default=0,
        help="Delay in seconds before DOI lookups (default: 0)",
    )
    parser.add_argument(
        "--user-agent-arxiv",
        metavar="USER_AGENT",
        type=str,
        default=None,
        help="User agent string for arXiv lookups (default: requests library default)",
    )
    parser.add_argument(
        "--user-agent-eprint",
        metavar="USER_AGENT",
        type=str,
        default=None,
        help="User agent string for ePrint lookups (default: requests library default)",
    )
    parser.add_argument(
        "--user-agent-doi",
        metavar="USER_AGENT",
        type=str,
        default=None,
        help="User agent string for DOI lookups (default: requests library default)",
    )


def set_lookup_config_from_args(args):
    """Validate the lookup options on parsed args and install them as the active config."""
    assert args.delay_dblp >= 0, "DBLP delay must be non-negative"
    assert args.delay_arxiv >= 0, "arXiv delay must be non-negative"
    assert args.delay_eprint >= 0, "ePrint delay must be non-negative"
    assert args.delay_doi >= 0, "DOI delay must be non-negative"

    config = LookupConfig()
    config.delay_dblp = args.delay_dblp
    config.delay_arxiv = args.delay_arxiv
    config.delay_eprint = args.delay_eprint
    config.delay_doi = args.delay_doi
    config.user_agent_arxiv = args.user_agent_arxiv
    config.user_agent_eprint = args.user_agent_eprint
    config.user_agent_doi = args.user_agent_doi
    set_lookup_config(config)
