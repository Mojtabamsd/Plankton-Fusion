import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import torch
import psutil
import seaborn as sns
import os


def report_to_df(report):
    report = [x.split(" ") for x in report.split("\n")]
    header = ["Class Name"] + [x for x in report[0] if x != ""]
    values = []
    for row in report[1:-1]:
        row = [value for value in row if value != ""]
        if row != []:
            while row.__len__() > header.__len__():
                tmp = list([row[0] + ' ' + row[1]])
                new_row = tmp + row[2:]
                row = new_row
            values.append(row)
    df = pd.DataFrame(data=values, columns=header)
    return df


def plot_loss(loss_values, num_epoch, training_path):
    # Create a plot of the loss values
    plt.figure(figsize=(10, 5))
    plt.plot(np.arange(1, num_epoch + 1), loss_values, label='Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training Loss Over Epochs')
    plt.legend()

    # Specify the path where you want to save the plot
    plot_path = training_path / 'loss_plot.png'

    # Save the plot to the specified path
    plt.savefig(plot_path)

    # display the plot using plt.show()
    # plt.show()

    # Close the plot to release resources
    plt.close()


def plot_results(report_df, cm, out_path, target_names):

    # Normalize the confusion matrix
    cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

    # Create a heatmap for the confusion matrix
    plt.figure(figsize=(16, 10))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap='Blues', xticklabels=target_names, yticklabels=target_names)

    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.title('Confusion Matrix')
    # plt.show()

    cm_path = os.path.join(out_path, 'confusion_matrix.png')
    plt.savefig(cm_path, dpi=600)

    # Extract class names and F1-scores
    class_names = report_df['Class Name'][:report_df.shape[0]-3]
    f1_scores = report_df['f1-score'][:report_df.shape[0]-3].astype(float)

    # Extract macro and weighted averages
    macro_avg = report_df.iloc[-2][2:].astype(float)
    weighted_avg = report_df.iloc[-1][2:].astype(float)  #

    # Create a bar chart
    plt.figure(figsize=(16, 10))

    # Plot class F1-scores
    plt.bar(class_names, f1_scores, color='skyblue', label='F1-Score')

    # Add a bar for Macro Average and Weighted Average
    plt.bar('Macro Avg', macro_avg['f1-score'], color='orange', label='Macro Avg')
    plt.bar('Weighted Avg', weighted_avg['f1-score'], color='green', label='Weighted Avg')

    plt.xlabel('Class Name')
    plt.ylabel('Scores')
    plt.title('Scores by Class')
    plt.xticks(rotation=45)
    plt.legend()
    # plt.show()

    cr_path = os.path.join(out_path, 'classification_report.png')
    plt.savefig(cr_path, dpi=600)


def memory_usage(config, model, device):

    # Create a dummy input tensor
    input_tensor = torch.randn((2, 1, config.sampling.target_size[0], config.sampling.target_size[1]))
    input_tensor = input_tensor.to(device)

    # Measure memory usage
    if device.type == 'cuda':
        # Measure GPU memory usage
        gpu_memory_before = torch.cuda.memory_allocated(device=device)
        _ = model(input_tensor)
        gpu_memory_after = torch.cuda.memory_allocated(device=device)
        gpu_memory_used = gpu_memory_after - gpu_memory_before

        return f"GPU Memory Used (MB): {gpu_memory_used / (1024 * 1024)}"
    else:
        # Measure CPU memory usage
        cpu_memory_before = psutil.virtual_memory().used
        _ = model(input_tensor)
        cpu_memory_after = psutil.virtual_memory().used
        cpu_memory_used = cpu_memory_after - cpu_memory_before

        return f"CPU Memory Used (MB): {cpu_memory_used / (1024 * 1024)}"
