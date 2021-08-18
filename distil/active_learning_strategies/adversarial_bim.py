import numpy as np
import torch
import torch.nn.functional as F
from .strategy import Strategy

class AdversarialBIM(Strategy):
    """
    Implements Adversial Bim Strategy which is motivated by the fact that often the distance
    computation from decision boundary is difficult and intractable for margin based methods. This 
    technique avoids estimating distance by using BIM(Basic Iterative Method)
    :footcite:`tramer2017ensemble` to estimate how much adversarial perturbation is required to 
    cross the boundary. Smaller the required the perturbation, closer the point is to the boundary.
 
    **Basic Iterative Method (BIM)**: Given a base input, the approach is to perturb each
    feature in the direction of the gradient by magnitude :math:`\\epsilon`, where is a
    parameter that determines perturbation size. For a model with loss
    :math:`\\nabla J(\\theta, x, y)`, where :math:`\\theta` represents the model parameters,
    x is the model input, and y is the label of x, the adversarial sample is generated
    iteratively as,
    .. math::
        \\begin{eqnarray}
            x^*_0 & = &x,
    
            x^*_i & = & clip_{x,e} (x^*_{i-1} + sign(\\nabla_{x^*_{i-1}} J(\\theta, x^*_{i-1} , y)))
        \\end{eqnarray}
    Parameters
    ----------
    X: numpy array
        Present training/labeled data   
    y: numpy array
        Labels of present training data
    unlabeled_x: numpy array
        Data without labels
    net: class
        Pytorch Model class
    handler: class
        Data Handler, which can load data even without labels.
    nclasses: int
        Number of unique target variables
    args: dict
        Specify optional parameters
        
        `batch_size`- Batch size to be used inside strategy class (int, optional)
        `eps`-epsilon value for gradients
    """
    
    def __init__(self, labeled_dataset, unlabeled_dataset, net, nclasses, args={}):
        """
        Constructor method
        """
        if 'eps' in args:
            self.eps = args['eps']
        else:
            self.eps = 0.05
            
        if 'verbose' in args:
            self.verbose = args['verbose']
        else:
            self.verbose = False
            
        if 'stop_iterations_by_count' in args:
            self.stop_iterations_by_count = args['stop_iterations_by_count']
        else:
            self.stop_iterations_by_count = 1000
        
        super(AdversarialBIM, self).__init__(labeled_dataset, unlabeled_dataset, net, nclasses, args={})

    def cal_dis(self, x):
        nx = torch.unsqueeze(x, 0).detach()
        nx.requires_grad_()
        eta = torch.zeros(nx.shape).to(self.device)

        out = self.model(nx+eta)
        py = out.max(1)[1]
        ny = out.max(1)[1]
        
        iteration = 0
        
        while py.item() == ny.item():
            
            if iteration == self.stop_iterations_by_count:
                break
            
            loss = self.loss(out, ny)
            loss.backward()

            eta += self.eps * torch.sign(nx.grad.data)
            nx.grad.data.zero_()

            out = self.model(nx+eta)
            py = out.max(1)[1]

            iteration += 1

        return (eta*eta).sum()

    def select(self, budget):
        """
        Selects next set of points
        Parameters
        ----------
        budget: int
            Number of indexes to be returned for next set
        Returns
        ----------
        idxs: list
            List of selected data point indexes with respect to unlabeled_x
        """	

        self.model.eval()
        self.model = self.model.to(self.device)
        
        dis = np.zeros(len(self.unlabeled_dataset))
        data_pool = self.unlabeled_dataset
        
        for i in range(len(self.unlabeled_dataset)):
            
            if self.verbose:
                if i % 5 == 0:
                    print('adv {}/{}'.format(i, len(self.unlabeled_dataset)))
            
            x = data_pool[i].to(self.device)
            dis[i] = self.cal_dis(x)
        
        idxs = dis.argsort()[:budget]
        return idxs