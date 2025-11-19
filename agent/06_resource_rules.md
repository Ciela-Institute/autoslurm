# **Resource Rules for GPU and CPU Jobs on Alliance (Compute Canada) Clusters**

This document describes the **principles and constraints** that agents must follow when choosing SLURM resources for CPU, GPU, memory, and runtime allocations. These rules reflect the standard scheduling policies of the Digital Research Alliance of Canada (formerly Compute Canada) HPC systems.

The goal is to ensure that generated SLURM job bundles are:

* cluster-friendly
* scheduler-efficient
* portable across Alliance systems
* aligned with typical allocation policies
* realistic for machine learning and scientific workloads

---

## **1. GPU Allocation Principles**

### **1.1 Request only the GPUs actually required**

GPU nodes are high-demand resources. Over-requesting GPUs:

* significantly increases queue time
* may violate fair-use allocation guidelines
* can block entire nodes unnecessarily

Agents must choose the smallest number of GPUs that is scientifically or computationally necessary.
Most jobs will require 1 GPU.
A node typically has 4 GPU at most.

### **1.2 Match GPU type only when required**

Some clusters contain multiple GPU models (e.g., V100, A100).
Specific GPU types should be requested only if:

* the workload relies on unique hardware features
* memory requirements are incompatible with smaller GPUs
* reproducibility requires identical GPU architecture

Otherwise, agents should remain agnostic to GPU type for faster scheduling.

---

## **2. CPU Allocation Principles**

### **2.1 Maintain a sensible CPU-to-GPU ratio**

Alliance documentation recommends pairing GPU requests with an appropriate number of CPUs.
Typical ML/AI workloads benefit from **~2–4 CPU cores per GPU**, depending on:

* dataloader behavior
* preprocessing overhead
* parallelism strategy
* cluster hardware characteristics

Agents should scale CPU allocations proportionally to GPU count unless the workload is known to be CPU-heavy or CPU-light.

### **2.2 Only request additional CPUs when necessary**

Extra CPUs consume node resources and increase queue wait times.
Agents should not exceed realistic CPU needs for the workload.

---

## **3. Memory Allocation Principles**

### **3.1 Choose memory appropriate for the workload**

Memory should:

* avoid OOM errors
* reflect dataset size and model size
* scale with GPU count and batch size
* stay within reasonable per-node limits

Typical guidelines:

* moderate ML jobs: **16–32 GB**
* large models or multi-GPU training: **64 GB or more**
* heavy data preprocessing: proportionally higher

### **3.2 Avoid requesting more memory than needed**

Over-requesting memory constrains the scheduler and increases queue time.

### **3.3 Follow node-level memory structure**

Some clusters have:

* fixed per-node memory
* per-core proportional memory
* GPU nodes with large unified memory pools

Agents should attempt to remain compatible with these layouts by choosing memory in reasonable increments.

---

## **4. Runtime (Walltime) Selection**

### **4.1 Bound runtime realistically**

Cluster scheduling performance depends heavily on providing accurate runtime estimates.

Guidelines:

* short tests or preprocessing: a few minutes to 1–4 hours
* single-GPU ML training: several hours to 1–2 days
* large multi-GPU jobs: typically 1–3 days

### **4.2 Avoid requesting maximum walltime when unnecessary**

Excessively long walltime requests:

* make jobs harder to schedule
* dramatically increase queue wait
* block usable node fragments

Agents should estimate runtime based on workload nature and size.

---

## **5. Job Arrays**

### **5.1 Use job arrays only when tasks are independent**

Job arrays are effective for:

* hyperparameter searches
* simulation ensembles
* multiple training seeds

They should **not** be used if tasks communicate or share state.

### **5.2 Keep array sizes reasonable**

Large arrays:

* place heavy load on the scheduler
* may hit cluster-level throttling policies
* require chunking strategies for large parameter sweeps

Agents should prefer moderately sized arrays or adopt batching if needed.

---

## **6. Tasks and Parallelism**

### **6.1 Use a single task for non-MPI workloads**

Most ML and GPU jobs:

* run on a single node
* do not use MPI
* do not need multiple distributed tasks

Agents must not allocate multiple tasks unless MPI or multi-process distributed training is explicitly required.

### **6.2 Request multi-task parallelism only with a clear purpose**

Multi-task jobs are needed for:

* MPI simulations
* distributed deep learning frameworks (DDP, Horovod)
* workflows that spawn many tightly coupled processes

Agents must align the number of tasks with the framework’s parallelism structure.

---

## **7. General Resource Allocation Guidelines**

### **7.1 Request only what the workload needs**

Efficient cluster usage improves:

* throughput
* fairness
* queue times for all users

Agents should build minimal, efficient resource bundles.

### **7.2 Align requests with cluster policies**

Different Alliance clusters may have:

* differing GPU counts per node
* different memory configurations
* different maximum walltimes
* different GPU types

Agents should attempt to remain portable by making conservative assumptions.

### **7.3 Always include a valid account/allocation**

Jobs must be charged to a research group’s allocation.
Agents should associate run bundles with the correct account label provided by the user or their project configuration.

---

## **8. Multi-Node or Advanced GPU Training (Optional Guidance)**

For multi-node deep learning or HPC simulations:

* nodes must be reserved consistently
* interconnect bandwidth matters
* CPU, GPU, and memory must be scaled jointly
* allocations become harder to schedule and should be used sparingly

Agents should only choose multi-node allocations when explicitly requested.

---

# **Summary**

Agents must create SLURM bundles that obey the following principles:

* **Request GPU, CPU, memory, and walltime resources conservatively and realistically.**
* **Follow Alliance cluster best practices:**

  * GPUs matched with sufficient CPUs
  * memory scaled to workload
  * bounded runtime
  * tasks matching the workload’s parallelism model
* **Use job arrays only for independent runs.**
* **Avoid over-requesting resources that increase queue time or violate fair-use policies.**
* **Maintain portability across different Alliance clusters.**

This ensures that autoslurm-generated jobs schedule efficiently, respect cluster norms, and remain fully compatible with national HPC infrastructures.
