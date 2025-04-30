import logging
from quart import Quart, abort, render_template, request, redirect, url_for
from typing import Optional
from sierra_ils_utils import SierraAPI, SierraDateTime

# configure logging
logging.basicConfig(
    level=logging.INFO,  # or DEBUG, WARNING, ERROR
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)  # Create a logger for this file/module

app = Quart(__name__)
app.config.from_object("config.Config")  # load config from config.py
                                         # Note: consider creating different config profiles
                                         #       e.g. Testing / Dev etc.
                                         #       https://quart.palletsprojects.com/en/latest/how_to_guides/configuration.html 

# configure the client
client = SierraAPI(
    base_url=app.config["SIERRA_API_BASE_URL"],
    client_id=app.config["SIERRA_API_CLIENT_KEY"],
    client_secret=app.config["SIERRA_API_CLIENT_SECRET"]
)


@app.route('/')
async def index():
    """
    Automatically redirect to the most recent title paging report.
    """
    return redirect(url_for('report'))


@app.route("/reports")
async def reports():
    try:
        response = await client.async_request("GET", "titlepaging/reports")
        response.raise_for_status()
        reports = response.json().get("entries", [])
    except Exception as e:
        logger.error(f"Failed to fetch reports: {e}")
        abort(500)
    
    return await render_template("reports.html", reports=reports)


from typing import Optional

@app.route("/report")
@app.route("/report/")
@app.route("/report/<int:report_id>")
async def report(report_id: Optional[int] = None):
    locationgroup = request.args.get("locationgroup", type=int)
    entries = []

    # Fetch all available locations for dropdown
    locationgroups = await get_locationgroups()

    # Only fetch report data if a location is selected
    if locationgroup is not None:
        # Get most recent report if no specific ID is provided
        if report_id is None:
            reports = await get_report_ids()
            if not reports:
                abort(404)
            reports.sort(key=lambda r: r.get('createdDate', '') or r.get('id', 0), reverse=True)
            report_id = reports[0]['id']

        limit = 2000
        offset = 0

        while True:
            try:
                response = await client.async_request(
                    "GET",
                    f"titlepaging/reports/{report_id}",
                    params={
                        "locationgroup": locationgroup,
                        "deleted": False,
                        "limit": limit,
                        "offset": offset
                    }
                )
                response.raise_for_status()
                data = response.json()
                batch = data.get("entries", [])
                entries.extend(batch)
                logger.info(f"Fetched {len(batch)} entries from offset {offset}")
                if len(batch) < limit:
                    break  # no more results
                offset += limit
            except Exception as e:
                logger.error(f"Error paginating report {report_id} at offset {offset}: {e}")
                abort(500)

    return await render_template(
        "report.html",
        entries=entries,
        report_id=report_id,
        locationgroup=locationgroup,
        locationgroups=locationgroups
    )



async def get_report_ids():
    try:
        response = await client.async_request("GET", "titlepaging/reports")
        response.raise_for_status()
        reports = response.json().get("entries", [])
    except Exception as e:
        logger.error(f"Failed to fetch reports: {e}")
        abort(500)
    
    return reports


async def get_locationgroups():
    limit = 50
    offset = 0
    locations = []

    while True:
        try:
            response = await client.async_request(
                'GET', 
                'branches/',
                params={
                    'limit': limit,
                    'offset': offset,
                    'fields': 'id,name'
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch location groups: {e}")
            return []

        entries = response.json().get('entries', [])
        if entries:
            locations.extend(entries)
            offset += limit
        else:
            break

    return locations