# Offline ideal correction

The minimum semantically valid correction keeps the four original files and changes only `server.js` content plus three complete plan fields. It maps existing files to all requested components, adds `preview`, makes `/health` explicit, and adds durable read/write operations using Node standard-library `fs` in `server.js`.

The real focal run had `allowed_replacements=[]`. Therefore this correction is valid against the project-plan validators but is not representable by that focal response scope: the required `server.js` replacement would be rejected before revalidation.
