import { backend } from "../../lib/api";

type Job = any;
type Outputs = any;
export default async function JobDetail({ params }: { params: { jobId: string } }) {
  const job: Job = await backend.job(params.jobId);
  const outputs: Outputs = await backend.outputs(params.jobId);

  return (
    <div>
      <h1>Job {job.job_id}</h1>
      <pre>{JSON.stringify(job.meta, null, 2)}</pre>

      <button onClick={() => backend.cancelJob(job.job_id)}>
        Cancel Job
      </button>

      <h2>Images</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)" }}>
        {outputs.images.map((img: string) => (
          <img key={img} src={`${process.env.NEXT_PUBLIC_BACKEND_URL}/${img}`} />
        ))}
      </div>
    </div>
  );
}
