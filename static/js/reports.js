let memberPaymentChart = null;
let currentMemberData = null;

function showMemberDetails(memberId) {
    const modal = document.getElementById('memberDetailsModal');
    
    // Fetch member details
    fetch(`/get_member_details/${memberId}`)
        .then(response => response.json())
        .then(data => {
            currentMemberData = {
                ...data,
                id: memberId  // Add the member ID to the stored data
            };
            document.getElementById('memberName').textContent = data.name;
            document.getElementById('totalDue').textContent = data.total_due.toFixed(2);
            document.getElementById('totalPaid').textContent = data.total_paid.toFixed(2);
            
            // Display payment history
            displayPaymentHistory(data.payments);
            

            // Show modal with animation
            modal.style.display = 'block';
            setTimeout(() => modal.classList.add('show'), 10);
        });
}

function displayPaymentHistory(payments, fromDate = null, toDate = null) {
    // Prepend the initial due row
    const [y, m, d] = currentMemberData.payment_date.split('-');
    const initialRow = `
        <tr>
            <td>${d}-${m}-${y}</td>
            <td>${currentMemberData.name}</td>
            <td style="color: #4CAF50;">+₹${currentMemberData.original_amount.toFixed(2)}</td>
            <td>No remarks</td>
        </tr>
    `;
    
    // Sort payment transactions by date (descending)
    let sortedPayments = [...payments].sort((a, b) => new Date(b.date) - new Date(a.date));
    
    // Apply date filtering if both dates are provided
    if (fromDate && toDate) {
        const from = new Date(fromDate);
        const to = new Date(toDate);
        sortedPayments = sortedPayments.filter(payment => {
            const pDate = new Date(payment.date);
            return pDate >= from && pDate <= to;
        });
    }
    
    const paymentRows = sortedPayments.map(payment => {
        const [yy, mm, dd] = payment.date.split('-');
        return `
            <tr>
                <td>${dd}-${mm}-${yy}</td>
                <td>${payment.name}</td>
                <td style="color: #FF5722;">-₹${payment.amount_paid.toFixed(2)}</td>
                <td>${payment.remarks}</td>
            </tr>
        `;
    }).join('');
    
    const historyHTML = initialRow + paymentRows;
    document.getElementById('paymentHistory').querySelector('tbody').innerHTML = historyHTML;
}

function filterPaymentHistory() {
    const fromDate = document.getElementById('historyDateFrom').value;
    const toDate = document.getElementById('historyDateTo').value;
    
    if (fromDate && toDate) {
        displayPaymentHistory(currentMemberData.payments, fromDate, toDate);
    }
}

function openPaymentHistoryInNewTab() {
    const memberId = currentMemberData.id;
    window.open(`/member_payment_history/${memberId}`, '_blank');
}

// Update the payment chart function
function updatePaymentChart(payments) {
    if (memberPaymentChart) {
        memberPaymentChart.destroy();
    }

    // Sort payments by date in ascending order
    const sortedPayments = [...payments].sort((a, b) => {
        return new Date(a.date) - new Date(b.date);
    });

    const ctx = document.getElementById('memberPaymentChart').getContext('2d');
    memberPaymentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sortedPayments.map(p => {
                const [year, month, day] = p.date.split('-');
                return `${day}-${month}-${year}`;
            }),
            datasets: [{
                label: 'Amount Paid',
                data: sortedPayments.map(p => p.amount_paid),
                backgroundColor: '#8A2BE2',
                borderColor: '#8A2BE2',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#1a2142'
                    },
                    ticks: { 
                        color: '#fff',
                        callback: function(value) {
                            return '₹' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        color: '#1a2142'
                    },
                    ticks: { 
                        color: '#fff',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            },
            plugins: {
                legend: {
                    labels: { 
                        color: '#fff',
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return '₹' + context.raw;
                        }
                    }
                }
            }
        }
    });
}

// Close modal functionality
document.addEventListener('DOMContentLoaded', function() {
    // Attach event listener to the close button within memberDetailsModal specifically
    const memberModalCloseBtn = document.querySelector('#memberDetailsModal .close-modal');
    if (memberModalCloseBtn) {
        memberModalCloseBtn.addEventListener('click', () => {
            const modal = document.getElementById('memberDetailsModal');
            modal.classList.remove('show');
            setTimeout(() => modal.style.display = 'none', 300);
        });
    }
    
    // Close memberDetailsModal when clicking outside of it
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('memberDetailsModal');
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.style.display = 'none', 300);
        }
    });
    
    // Attach event listener for the edit transaction modal close button
    const editModalCloseBtn = document.getElementById('closeEditModal');
    if (editModalCloseBtn) {
        editModalCloseBtn.addEventListener('click', closeEditModal);
    }
    
    // Close editTransactionModal when clicking outside of it
    window.addEventListener('click', (e) => {
        const editModal = document.getElementById('editTransactionModal');
        if (e.target === editModal) {
            closeEditModal();
        }
    });
});

function editTransaction(transactionId) {
    const modal = document.getElementById('editTransactionModal');
    
    // Fetch transaction details
    fetch(`/get_transaction/${transactionId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Populate form fields
                document.getElementById('editTransactionId').value = data.transaction.id;
                document.getElementById('editMember').value = data.transaction.member_id;
                document.getElementById('editDate').value = data.transaction.date;
                document.getElementById('editAmount').value = data.transaction.amount;
                
                // Show modal
                modal.style.display = 'block';
                setTimeout(() => modal.classList.add('show'), 10);
            } else {
                alert('Error loading transaction details');
            }
        })
        .catch(error => {
            console.error('Error fetching transaction:', error);
            alert('Error loading transaction details');
        });
}

function closeEditModal() {
    const modal = document.getElementById('editTransactionModal');
    modal.classList.remove('show');
    setTimeout(() => modal.style.display = 'none', 300);
}

// Add form submission handler
document.getElementById('editTransactionForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const transactionId = document.getElementById('editTransactionId').value;
    const data = {
        member_id: document.getElementById('editMember').value,
        payment_date: document.getElementById('editDate').value,
        amount_paid: parseFloat(document.getElementById('editAmount').value)
    };
    
    fetch(`/update_transaction/${transactionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            closeEditModal();
            // Reload the page to show updated data
            window.location.reload();
        } else {
            alert('Error updating transaction: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating transaction');
    });
});
